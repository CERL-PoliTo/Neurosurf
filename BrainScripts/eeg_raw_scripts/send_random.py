"""
Sends as an LSL stream a random signal.

Example:
    send_random <num_channels> <stream_name>
"""

import argparse
from pylsl import StreamInfo, StreamOutlet, cf_float32
import time
import numpy as np

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SAMPLING_RATE = 125  # [Hz] sampling rate of the generated signal
LSL_SOURCE_ID = "myuid34234"

# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("num_channels", type=int)
    ap.add_argument("stream_name")
    args = ap.parse_args()

    num_channels = args.num_channels
    stream_name = args.stream_name

    if num_channels <= 0:
        raise ValueError("num_channels must be a positive integer.")

    print(f"num_channels: {num_channels}, stream_name: {stream_name}")

    # --- LSL Setup ----------------------------------------------------------
    info = StreamInfo(
        stream_name, "EEG", num_channels, SAMPLING_RATE, cf_float32, LSL_SOURCE_ID
    )
    outlet = StreamOutlet(info)

    # --- Processing loop ----------------------------------------------------
    period = 1.0 / SAMPLING_RATE
    while True:
        start_time = time.perf_counter()
        outlet.push_sample(np.random.rand(num_channels).astype(np.float32).tolist())
        sleep_amount = period - (time.perf_counter() - start_time)
        if sleep_amount > 0:
            time.sleep(sleep_amount)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
