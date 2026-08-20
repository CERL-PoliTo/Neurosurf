"""
Real-time source localization.

Reads an EEG LSL stream, centers each batch, applies a precomputed linear inverse,
and streams dipole activations to an LSL outlet named 'BrainSurface'.

Set SOURCE_LOCALIZATION_METHOD to either:
- "sLORETA"
- "wMNE"
"""

import argparse
import collections
import sys
import time

import h5py
import numpy as np
from pylsl import StreamInlet, IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_float32
from pylsl.resolve import resolve_stream

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_SAMPLES_TO_PROCESS = 2  # Number of samples to process at once while applying the source localization algorithm
MAX_BUFFER_LEN = 2  # [s] or, if the stream has IRREGULAR_RATE, [#samples*100]. Buffer length for the inlet stream
LSL_SOURCE_ID = "uid45678890"

SOURCE_LOCALIZATION_METHOD = "sLORETA"  # "sLORETA" or "wMNE"

SCALING = 20000 if SOURCE_LOCALIZATION_METHOD == "sLORETA" else 200
LAMBDA_SCALE = 0.01

WMNE_DEPTH_EXPONENT = 0.5
WMNE_MAX_WEIGHT = 10.0

EPS = 1e-12


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def load_leadfield(path: str) -> np.ndarray:
    try:
        with h5py.File(path, "r") as f:
            if "Leadfield" not in f:
                raise KeyError("Dataset 'Leadfield' not found in HDF5 file.")
            G = np.array(f["Leadfield"]).T
    except Exception as e:
        print(f"Failed to open/parse leadfield '{path}': {e}")
        sys.exit(1)
    return G


def build_transforms(G: np.ndarray):
    """Precompute the inverse operator and method-dependent normalization vector."""
    method = SOURCE_LOCALIZATION_METHOD.upper()

    num_channels, num_dipoles = G.shape

    G -= G.mean(axis=0, keepdims=True)  # zero averaging
    _lambda = LAMBDA_SCALE * (np.linalg.norm(G, 2) ** 2)

    if method == "SLORETA":
        G_inv = np.linalg.solve(
            (G @ G.T + _lambda * np.eye(num_channels)).T,
            G
        ).T

        diagSj = np.sum(G_inv * G.T, axis=1)  # diag(G_inv @ G)
        denom = np.where(diagSj == 0, EPS, diagSj)  # avoid div-by-zero
        inv_denom = 1.0 / denom

    elif method == "WMNE":
        column_norms = np.linalg.norm(G, axis=0)
        max_norm = max(np.max(column_norms), EPS)

        relative_norms = np.where(column_norms == 0, EPS, column_norms) / max_norm
        source_weights = 1.0 / (relative_norms ** WMNE_DEPTH_EXPONENT)
        source_weights = np.clip(source_weights, 1.0, WMNE_MAX_WEIGHT)

        # Weighted MNE inverse:
        # G_inv = R G.T (G R G.T + lambda I)^-1
        # with diagonal R implemented through source_weights.
        GR = G * source_weights[None, :]

        G_inv = np.linalg.solve(
            (GR @ G.T + _lambda * np.eye(num_channels)).T,
            GR
        ).T

        inv_denom = np.ones(num_dipoles, dtype=np.float32)

    else:
        print(
            f"Unknown SOURCE_LOCALIZATION_METHOD '{SOURCE_LOCALIZATION_METHOD}'. "
            "Use 'sLORETA' or 'wMNE'."
        )
        sys.exit(1)

    return G_inv.astype(np.float32), inv_denom.astype(np.float32)


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("leadfield_filename")
    ap.add_argument("input_LSL_stream")
    ap.add_argument("output_LSL_stream")
    args = ap.parse_args()

    leadfield_filename = args.leadfield_filename
    input_LSL_stream = args.input_LSL_stream
    output_LSL_stream = args.output_LSL_stream

    print("Starting source localization")
    print(f"Using {SOURCE_LOCALIZATION_METHOD}")

    G = load_leadfield(leadfield_filename)
    num_channels, num_dipoles = G.shape
    G_inv, inv_denom = build_transforms(G)

    # --- LSL Setup ----------------------------------------------------------
    print("looking for an EEG stream...")
    streams = resolve_stream("name", input_LSL_stream)
    if len(streams) > 1:
        print("WARNING: multiple EEG streams found, using first one")

    selected_stream = streams[0]
    inlet = StreamInlet(selected_stream, MAX_BUFFER_LEN)
    print("Stream sample type is {0}".format(inlet.sample_type))

    samples_to_send = num_dipoles
    info = StreamInfo(
        output_LSL_stream,
        "Brain",
        samples_to_send,
        IRREGULAR_RATE,
        cf_float32,
        LSL_SOURCE_ID,
    )
    outlet = StreamOutlet(info)

    # --- Source Localization Setup -----------------------------------------
    Vm = np.empty((num_channels, MAX_SAMPLES_TO_PROCESS), dtype=np.float32)
    Xest = np.zeros((num_dipoles, MAX_SAMPLES_TO_PROCESS), dtype=np.float32)
    XsLOt = np.zeros((num_dipoles, MAX_SAMPLES_TO_PROCESS), dtype=np.float32)
    send_buf = np.empty(num_dipoles, dtype=np.float32)
    means = np.empty((1, MAX_SAMPLES_TO_PROCESS), dtype=np.float32)

    loop_runtimes = collections.deque(maxlen=10)

    step = 0

    # --- Processing loop ----------------------------------------------------
    print("starting loop")
    while True:
        loop_start_time = time.perf_counter()

        # Collect data via LSL
        samples_received = 0
        while samples_received < MAX_SAMPLES_TO_PROCESS:
            sample, timestamp = inlet.pull_sample(timeout=1.0)
            if sample is None:
                continue
            if len(sample) != num_channels:
                print(
                    "\tReceived sample's size {0} instead of {1}".format(
                        len(sample), num_channels
                    )
                )
                continue
            Vm[:, samples_received] = sample
            samples_received += 1

        # Zero-average per time sample
        np.mean(Vm, axis=0, keepdims=True, out=means)
        np.subtract(Vm, means, out=Vm)

        # Inverse solution and method-dependent normalization
        np.dot(G_inv, Vm, out=Xest)
        np.multiply(Xest, Xest, out=XsLOt)
        XsLOt *= inv_denom[:, None]

        # Rescale and push one sample at a time
        for i in range(samples_received):
            np.copyto(send_buf, XsLOt[:, i], casting="unsafe")
            np.divide(send_buf, SCALING, out=send_buf)
            np.clip(send_buf, 0.0, 1.0, out=send_buf)
            outlet.push_sample(send_buf.tolist())

        elapsed_time = time.perf_counter() - loop_start_time
        loop_runtimes.append(elapsed_time)
        fps = float(1.0 / (sum(loop_runtimes) / len(loop_runtimes)))
        print(f"\r{int(fps)} FPS", end="", flush=True)

        step += 1


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
