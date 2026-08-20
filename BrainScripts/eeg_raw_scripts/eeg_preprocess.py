"""
Reads an EEG LSL stream, applies preprocessing operations, then republishes.

Example:
    eeg_preprocess <input_LSL_stream> <output_LSL_stream-name>
"""

import argparse

import numpy as np
from pylsl import (
    StreamInlet,
    StreamInfo,
    StreamOutlet,
    FOREVER,
    cf_float32,
)
from pylsl.resolve import resolve_stream

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SCALING = 500  # uV
OFFSET = 0.15  # applied after the scaling
MAX_BUFFER_LEN = 2  # [s] or, if the stream has IRREGULAR_RATE, [#samples*100]. Buffer length for the inlet stream
LSL_SOURCE_ID = "uid45678879"

# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_LSL_stream")
    ap.add_argument("output_LSL_stream")
    args = ap.parse_args()

    input_LSL_stream = args.input_LSL_stream
    output_LSL_stream = args.output_LSL_stream

    # --- LSL Setup ----------------------------------------------------------
    print("Starting EEG preprocessing")
    print("looking for an EEG stream...")
    streams = resolve_stream("name", input_LSL_stream)

    if len(streams) > 1:
        print("WARNING: multiple EEG streams found, using first one")

    selected_stream = streams[0]
    num_channels = selected_stream.channel_count()
    sampling_rate = selected_stream.nominal_srate()
    inlet = StreamInlet(selected_stream, MAX_BUFFER_LEN)

    info = StreamInfo(
        output_LSL_stream,
        "EEG",
        num_channels,
        sampling_rate,
        cf_float32,
        LSL_SOURCE_ID,
    )
    outlet = StreamOutlet(info)

    # --- Processing loop ----------------------------------------------------
    while True:
        sample, timestamp = inlet.pull_sample(timeout=FOREVER)
        if sample is None:
            continue
        if len(sample) != num_channels:
            print("WARNING: unexpected number of channels in sample")
            continue

        sample = np.array(sample, dtype=np.float32)
        sample /= SCALING
        sample += OFFSET
        np.clip(sample, 0.0, 1.0, out=sample)
        outlet.push_sample(sample.tolist(), timestamp=timestamp)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
