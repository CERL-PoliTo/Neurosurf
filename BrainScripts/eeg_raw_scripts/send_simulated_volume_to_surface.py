"""
Stream simulated EEG from a leadfield with one dipole driven more strongly.

Usage:
    send_leadfield <leadfield_filename> <source_dipole> <stream_name>
"""

import argparse
import os
import time

import h5py
import numpy as np
from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_float32

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
SAMPLING_RATE = 100  # [Hz]
LSL_SOURCE_ID = "uid4567884154"

STARTING_NOISE = 0.1  # initial noise scale
ONLINE_NOISE = 0.01  # per-step random drift
SOURCE_NOISE = 1.0  # extra noise on the active source

NORMALIZE_EPS = 1e-12  # avoid division by 0 on normalization


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Send leadfield-based simulated EEG over LSL."
    )
    ap.add_argument("leadfield_filename")
    ap.add_argument("source_dipole", type=int)
    ap.add_argument("stream_name")
    args = ap.parse_args()

    leadfield_filename = args.leadfield_filename
    source_dipole = args.source_dipole
    stream_name = args.stream_name

    if not os.path.exists(leadfield_filename):
        raise FileNotFoundError(
            f"Leadfield file '{os.path.abspath(leadfield_filename)}' not found."
        )

    with h5py.File(leadfield_filename, "r") as h5:
        if "Leadfield" not in h5:
            raise KeyError("Dataset 'Leadfield' not found in the HDF5 file.")
        G = np.asarray(h5["Leadfield"]).T

    num_channels, num_dipoles = G.shape
    G -= G.mean(axis=0, keepdims=True)  # zero averaging

    if not (0 <= source_dipole < num_dipoles):
        raise ValueError(
            f"source_dipole must be in [0, {num_dipoles - 1}], got {source_dipole}."
        )

    # --- LSL Setup ----------------------------------------------------------
    info = StreamInfo(
        stream_name, "EEG", num_channels, IRREGULAR_RATE, cf_float32, LSL_SOURCE_ID
    )
    outlet = StreamOutlet(info)

    rng = np.random.default_rng()
    source_activity = rng.uniform(-0.5, 0.5, size=num_dipoles) * STARTING_NOISE

    # Normalization parameters (frozen from first step)
    min0 = None
    range0 = None

    period = 1.0 / SAMPLING_RATE
    step = 0

    # --- Processing loop ----------------------------------------------------
    while True:
        start_time = time.perf_counter()

        # Bound baseline activity
        np.clip(
            source_activity,
            -STARTING_NOISE / 2.0,
            STARTING_NOISE / 2.0,
            out=source_activity,
        )
        source_activity += rng.random(num_dipoles) * ONLINE_NOISE - (ONLINE_NOISE / 2.0)

        # Drive the chosen dipole
        if step == 0:
            source_activity[source_dipole] = STARTING_NOISE + SOURCE_NOISE
        else:
            source_activity[source_dipole] += rng.uniform(-0.5, 0.5) * SOURCE_NOISE

        # Forward model to electrodes
        samples = G @ source_activity  # shape: (num_channels,)

        # Freeze normalization on first step, then reuse
        if step == 0:
            min0 = float(np.min(samples))
            max0 = float(np.max(samples))
            range0 = max(max0 - min0, NORMALIZE_EPS)

        samples = (samples - min0) / range0
        np.clip(samples, 0.0, 1.0, out=samples)

        # Push as float32 with explicit timestamp
        outlet.push_sample(samples.astype(np.float32).tolist())

        # Pace the loop
        sleep_amount = period - (time.perf_counter() - start_time)
        if sleep_amount > 0:
            time.sleep(sleep_amount)

        step += 1


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
