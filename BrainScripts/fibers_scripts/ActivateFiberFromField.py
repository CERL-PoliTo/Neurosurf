"""
Real-time fiber activation streaming over LSL.

This script:
- Reads a leadfield matrix from an HDF5 file.
- Listens to an EEG-related LSL stream (e.g., 'BrainSurface').
- Computes potential differences along white-matter fibers.
- Streams fiber activations over LSL for consumption (e.g., by Unity).

Expected HDF5 layout
--------------------
Dataset "Leadfield": shape (N_dipoles, 2 * N_fibers)
Each pair of columns corresponds to the two extremities of a fiber.
"""

import argparse
import collections
import os
import time

import h5py
import numpy as np
from pylsl import (
    StreamInlet,
    StreamInfo,
    StreamOutlet,
    cf_float32,
)
from pylsl.resolve import resolve_stream


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

OUTPUT_RATE: float = 1000.0  # [Hz]
LSL_PULL_TIMEOUT: float = 1.0  # [s]
FPS_AVG_WINDOW: int = 10
MAX_BUFFER_LEN: int = 2  # [s] Buffer length for the inlet stream
LSL_SOURCE_ID: str = "uidfibersv0912"
MAX_SAMPLES_TO_PROCESS: int = 1

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _load_leadfield(path: str):
    """Load leadfield matrix from HDF5 and infer fiber/dipole dimensions."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Leadfield file '{os.path.abspath(path)}' not found.")

    with h5py.File(path, "r") as f:
        if "Leadfield" not in f:
            raise KeyError(
                f"Dataset 'Leadfield' not found in '{os.path.abspath(path)}'."
            )
        G = np.array(f["Leadfield"], dtype=float)

    if G.shape[1] % 2 == 0:
        # shape (N_dipoles, 2*N_fibers) -> transpose
        G = G.T
        n_fibers = G.shape[0] // 2
        n_dipoles = G.shape[1]
    else:
        raise ValueError(
            "Leadfield shape is incompatible with (N_dipoles, 2*N_fibers). "
            f"Got {G.shape}."
        )

    return G, n_fibers, n_dipoles


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

    print("Starting fiber script")
    print("Loading leadfield data...")
    G, num_fibers, num_dipoles = _load_leadfield(leadfield_filename)

    # --- LSL Setup ----------------------------------------------------------
    print("looking for source stream...")
    streams = resolve_stream("name", input_LSL_stream)
    if len(streams) > 1:
        print("WARNING: multiple EEG streams found, using first one")

    selected_stream = streams[0]
    inlet = StreamInlet(selected_stream, MAX_BUFFER_LEN)
    print("Stream sample type is {0}".format(inlet.sample_type))

    info = StreamInfo(
        output_LSL_stream,
        "Fibers",
        num_fibers,
        OUTPUT_RATE,
        cf_float32,
        LSL_SOURCE_ID,
    )
    outlet = StreamOutlet(info)

    # --- Forward setup ------------------------------------------------------
    X = np.empty((num_dipoles, MAX_SAMPLES_TO_PROCESS))
    pot = np.empty((num_fibers * 2, MAX_SAMPLES_TO_PROCESS))
    diff_pot = np.empty((num_fibers, MAX_SAMPLES_TO_PROCESS))
    send_buf = np.empty(num_fibers, dtype=np.float32)

    loop_runtimes = collections.deque(maxlen=FPS_AVG_WINDOW)

    # --- Processing loop ----------------------------------------------------
    print("starting loop")
    while True:
        loop_start_time = time.perf_counter()

        # Collect data via LSL
        samples_received = 0
        while samples_received < MAX_SAMPLES_TO_PROCESS:
            samples, timestamp = inlet.pull_sample(timeout=LSL_PULL_TIMEOUT)
            if samples is None:
                continue
            if len(samples) != num_dipoles:
                print(
                    "\tReceived sample's size {0} instead of {1}".format(
                        len(samples), num_dipoles
                    )
                )
                continue
            X[:, samples_received] = samples
            samples_received += 1

        # Compute the fibers' potential difference between extremities
        np.dot(G, X, out=pot)
        np.subtract(pot[0::2, :], pot[1::2, :], out=diff_pot)
        np.absolute(diff_pot, out=diff_pot)

        for i in range(samples_received):
            np.copyto(send_buf, diff_pot[:, i])
            outlet.push_sample(send_buf.tolist())

        elapsed_time = time.perf_counter() - loop_start_time
        loop_runtimes.append(elapsed_time)
        fps = float(1.0 / (sum(loop_runtimes) / len(loop_runtimes)))
        print(f"\r{int(fps)} FPS", end="", flush=True)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
