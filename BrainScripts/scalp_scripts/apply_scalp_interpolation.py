"""
Perform scalp interpolation of the incoming LSL stream, post-process, and send the results over another stream
"""

import argparse
import collections
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import pylsl
from pylsl import StreamInlet, IRREGULAR_RATE, StreamInfo, StreamOutlet, FOREVER
from pylsl.resolve import resolve_stream

import scalp_interpolation_core as sc

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

DEBUG = False
MAX_BUFFER_LEN = 2  # [s] or, if the stream has IRREGULAR_RATE, [#samples*100]. Buffer length for the inlet stream
SOURCE_ID = "uid45678891"
INTERP_ORDER = 4
DISTANCE_TOL = 1.4
MIN_PRECISION = 1e-4


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scalp_mesh_filename")
    ap.add_argument("electrode_pos_filename")
    ap.add_argument("input_LSL_stream")
    ap.add_argument("output_LSL_stream")
    ap.add_argument(
        "--cut-below-z",
        type=float,
        default=None,
        help="If provided, vertices below this y-coordinate are marked as non-covered.",
    )
    args = ap.parse_args()

    scalp_mesh_filename = args.scalp_mesh_filename
    electrode_pos_filename = args.electrode_pos_filename
    input_LSL_stream = args.input_LSL_stream
    output_LSL_stream = args.output_LSL_stream
    cut_below_z = args.cut_below_z

    print("Starting scalp interpolation")
    print("Reading scalp mesh file")
    try:
        mesh = np.loadtxt(scalp_mesh_filename)
    except Exception as e:
        print(f"Error reading mesh '{scalp_mesh_filename}': {e}")
        sys.exit(1)

    if mesh.ndim != 2 or mesh.shape[1] != 3:
        print("Scalp mesh must be a 2D array with 3 columns.")
        sys.exit(1)

    try:
        scalp_num_vertices = int(mesh[0, 0])
    except ValueError:
        print("Scalp mesh format is incorrect")
        sys.exit(1)
    if scalp_num_vertices + 2 > mesh.shape[0]:
        print("Scalp mesh file is too short for the declared number of vertices.")
        sys.exit(1)
    vertices = mesh[1 : scalp_num_vertices + 1, :]
    num_scalp_vertices = vertices.shape[0]

    try:
        electrode_pos = np.loadtxt(
            electrode_pos_filename, dtype=float
        )  # (N x 3) float values
    except Exception as e:
        print(f"Error reading electrode positions '{electrode_pos_filename}': {e}")
        sys.exit(1)
    if electrode_pos.ndim != 2 or electrode_pos.shape[1] != 3:
        print("Electrode positions file must be N x 3.")
        sys.exit(1)
    num_channels = electrode_pos.shape[0]

    # --- LSL Setup ----------------------------------------------------------
    print("looking for an EEG stream...")
    streams = resolve_stream("name", input_LSL_stream)
    if len(streams) > 1:
        print("WARNING: multiple EEG streams found, using first one")
    selected_stream = streams[0]
    inlet = StreamInlet(selected_stream, MAX_BUFFER_LEN)

    info = StreamInfo(
        output_LSL_stream,
        "Scalp",
        num_scalp_vertices,
        IRREGULAR_RATE,
        pylsl.cf_float32,
        SOURCE_ID,
    )
    outlet = StreamOutlet(info)

    if DEBUG:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2])
        ax.scatter(
            electrode_pos[:, 0],
            electrode_pos[:, 1],
            electrode_pos[:, 2],
            c="red",
            marker="*",
        )
        plt.show()

    # --- Scalp interpolation setup ------------------------------------------
    """
    Setup the interpolation matrices
    G_scalp will interpolate to all the points in coord
    G_electrodes will interpolate on the electrodes, only useful to check that the interpolation is working properly.
    G_system is used to determine the interpolation coefficients.
    """
    G_system, G_electrodes, G_scalp = sc.setup(
        INTERP_ORDER, vertices.T, electrode_pos.T
    )

    # compute minimum distance between electrodes with some tolerance
    # NOTE: not using cKDTree for code clarity here since the mesh used are not too big
    diff_e = electrode_pos[:, None, :] - electrode_pos[None, :, :]
    sqdist_e = np.einsum("ijk,ijk->ij", diff_e, diff_e)
    np.fill_diagonal(sqdist_e, np.inf)  # ignore self-distances on the diagonal
    min_sqdist = np.min(sqdist_e)
    distance_tolerance = np.sqrt(min_sqdist) * DISTANCE_TOL

    # distances from every vertex to every electrode
    diff_v = vertices[:, None, :] - electrode_pos[None, :, :]
    sqdist_v = np.einsum("ijk,ijk->ij", diff_v, diff_v)

    covered_mask = (sqdist_v < distance_tolerance**2).any(axis=1)

    if cut_below_z is not None:
        below_cut_mask = vertices[:, 2] < cut_below_z
        covered_mask[below_cut_mask] = False

    covered_area = set(np.flatnonzero(covered_mask))
    non_covered_area = np.flatnonzero(~covered_mask).tolist()

    # --- Processing loop ----------------------------------------------------
    loop_runtimes = collections.deque(maxlen=10)
    step = 0
    while True:
        loop_start_time = time.perf_counter()
        samples, timestamp = inlet.pull_sample(timeout=FOREVER)
        if samples is None:
            continue
        if len(samples) != num_channels:
            raise RuntimeError(f"Expected {num_channels} channels, got {len(samples)}")
        samples = np.reshape(np.array(samples), (len(samples), 1))

        interpolation_coefs = sc.get_interpolation_coefs(G_system, samples)
        interpolated_measurements = sc.get_interpolated_data(
            interpolation_coefs, G_scalp
        ).astype(np.float32, copy=False)

        # --- Post-processing ----------------------------------------------------
        # Zeroing out the points too far from the electrodes since they are typically only artifacts
        interpolated_measurements = np.abs(interpolated_measurements)
        # interpolated_measurements = np.log(interpolated_measurements) # For log scale display
        interpolated_measurements[non_covered_area] = 0.0
        np.clip(interpolated_measurements, 0.0, 1.0, out=interpolated_measurements)
        outlet.push_sample(interpolated_measurements.reshape(-1).tolist())

        step += 1

        elapsed_time = time.perf_counter() - loop_start_time
        loop_runtimes.append(elapsed_time)
        fps = float(1.0 / (sum(loop_runtimes) / len(loop_runtimes)))
        print(f"\r{int(fps)} FPS", end="", flush=True)

        if DEBUG:
            interpolated_measurements_electrodes = sc.get_interpolated_data(
                interpolation_coefs, G_electrodes
            )
            rel_error = np.linalg.norm(
                interpolated_measurements_electrodes - samples
            ) / np.linalg.norm(samples)
            if rel_error > MIN_PRECISION:
                print("Warning: interpolation is not working on this dataset!\n")
            if step % 100 == 0:
                fig = plt.figure()
                ax = fig.add_subplot(111, projection="3d")
                sub1 = ax.scatter(
                    vertices[:, 0],
                    vertices[:, 1],
                    vertices[:, 2],
                    c=interpolated_measurements[:, 0],
                )
                sub2 = ax.scatter(
                    electrode_pos[:, 0],
                    electrode_pos[:, 1],
                    electrode_pos[:, 2],
                    c=samples[:, 0],
                    marker="*",
                    s=500,
                )
                plt.colorbar(sub1)
                plt.colorbar(sub2)
                plt.show()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
