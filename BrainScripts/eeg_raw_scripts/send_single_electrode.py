"""
Activate one electrode at random for a few samples, then change it.

Usage:
    send_single_electrode <num_channels> <stream_name> <active_electrode>

Notes:
- Set <active_electrode> to -1 to randomize a new electrode every CHANGE_RATE samples.
- Otherwise pass a channel index to keep that electrode active continuously.
"""

import argparse
import random
import time

import numpy as np
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

CHANGE_RATE = 2000  # samples before switching electrode when randomizing
SAMPLING_RATE = 1000  # [Hz]
LSL_SOURCE_ID = "myuid34234"


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("num_channels", type=int)
    ap.add_argument("stream_name")
    ap.add_argument("active_electrode", type=int)
    args = ap.parse_args()

    num_channels = args.num_channels
    stream_name = args.stream_name
    active_electrode = args.active_electrode

    if num_channels <= 0:
        raise ValueError("num_channels must be a positive integer.")
    if active_electrode != -1 and not (0 <= active_electrode < num_channels):
        raise ValueError(
            f"active_electrode must be -1 or in [0, {num_channels - 1}], got {active_electrode}."
        )

    # --- LSL Setup ----------------------------------------------------------
    info = StreamInfo(
        stream_name, "EEG", num_channels, SAMPLING_RATE, cf_float32, LSL_SOURCE_ID
    )
    outlet = StreamOutlet(info)

    # --- Processing loop ----------------------------------------------------
    print("now sending data (single electrode)...")
    period = 1.0 / SAMPLING_RATE

    while True:
        # Choose electrode: fixed if provided, else random for this block
        electrode_index = (
            random.randint(0, num_channels - 1)
            if active_electrode == -1
            else active_electrode
        )
        print(f"electrode {electrode_index}")

        for _ in range(CHANGE_RATE):
            start = time.perf_counter()

            samples = np.zeros(num_channels, dtype=np.float32)
            samples[electrode_index] = 1.0

            outlet.push_sample(samples.tolist())

            sleep_amount = period - (time.perf_counter() - start)
            if sleep_amount > 0:
                time.sleep(sleep_amount)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
