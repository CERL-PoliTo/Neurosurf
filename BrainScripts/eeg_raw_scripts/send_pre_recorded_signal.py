"""
Sends as an LSL stream a prerecorded signal stored in a given HDF5 file.

Example:
    send_pre_recorded_signal <signal_filename> <stream_name>
"""

import argparse
import time

import h5py
import numpy as np
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SAMPLING_RATE = 125  # [Hz] sampling rate of the prerecorded signal
LSL_SOURCE_ID = "myuid34234"

# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("signal_filename")
    ap.add_argument("stream_name")
    args = ap.parse_args()

    signal_filename = args.signal_filename
    stream_name = args.stream_name

    with h5py.File(signal_filename, "r") as hd5f:
        if "data" not in hd5f:
            raise KeyError("Dataset 'data' not found in HDF5 file.")
        print("Sending pre-recorded signal from {0}".format(signal_filename))
        prerecorded_signal = hd5f.get("data")
        prerecorded_signal = np.asarray(prerecorded_signal, dtype=np.float32).T

    num_channels, num_samples = prerecorded_signal.shape

    # --- LSL Setup ----------------------------------------------------------
    info = StreamInfo(
        stream_name, "EEG", num_channels, SAMPLING_RATE, cf_float32, LSL_SOURCE_ID
    )
    outlet = StreamOutlet(info)

    # --- Processing loop ----------------------------------------------------
    period = 1.0 / SAMPLING_RATE

    while True:
        start_time = time.perf_counter()
        for i in range(num_samples):
            outlet.push_sample(prerecorded_signal[:, i].tolist())
            sleep_amount = period - (time.perf_counter() - start_time - i * period)
            if sleep_amount > 0:
                time.sleep(sleep_amount)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
