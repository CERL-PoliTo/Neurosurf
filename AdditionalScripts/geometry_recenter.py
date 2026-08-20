"""
Recenter (and optionally rescale) a scalp mesh + electrode coordinates for Perrin spherical spline interpolation.

Default behavior:
- Fit a sphere to the scalp vertices (least squares)
- Transform both vertices and electrodes: (p - center) / radius
- Save updated files so interpolation can assume geometry is centered once-and-for-all.

Mesh format expectation (matches your main script):
- Numeric text file readable by np.loadtxt
- First numeric row: mesh[0, 0] = number of scalp vertices (int)
- Next N rows: vertex coordinates (x y z)  => these will be transformed
- Remaining rows (if any): left untouched

Electrode positions file:
- N x 3 numeric text file readable by np.loadtxt
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Literal, Tuple

import numpy as np


FitTarget = Literal["vertices", "electrodes", "both"]
Method = Literal["sphere", "centroid"]


def fit_sphere(points_xyz: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Least-squares fit of a sphere to points.
    Returns (center, radius).
    """
    if points_xyz.ndim != 2 or points_xyz.shape[1] != 3:
        raise ValueError("fit_sphere expects an (N, 3) array.")

    x, y, z = points_xyz[:, 0], points_xyz[:, 1], points_xyz[:, 2]
    A = np.c_[2 * x, 2 * y, 2 * z, np.ones(points_xyz.shape[0])]
    b = x * x + y * y + z * z

    cx, cy, cz, d = np.linalg.lstsq(A, b, rcond=None)[0]
    center = np.array([cx, cy, cz], dtype=float)
    radius = float(np.sqrt(d + cx * cx + cy * cy + cz * cz))

    if not np.isfinite(radius) or radius <= 0:
        raise ValueError(f"Invalid fitted radius: {radius}")

    return center, radius


def load_mesh(mesh_path: str) -> Tuple[np.ndarray, int]:
    """
    Loads the mesh numerically via np.loadtxt and returns (mesh_numeric, n_vertices).

    mesh_numeric is 2D with shape (R, 3) expected.
    n_vertices comes from mesh_numeric[0, 0].
    """
    mesh = np.loadtxt(mesh_path, dtype=float)
    if mesh.ndim != 2 or mesh.shape[1] != 3:
        raise ValueError("Scalp mesh must be a 2D array with 3 columns (numeric text).")

    n_vertices = int(mesh[0, 0])
    if n_vertices <= 0:
        raise ValueError(f"Invalid vertex count in mesh header: {n_vertices}")

    if 1 + n_vertices > mesh.shape[0]:
        raise ValueError(
            f"Mesh too short: header says {n_vertices} vertices, "
            f"but file has only {mesh.shape[0] - 1} rows after header."
        )

    return mesh, n_vertices


def load_electrodes(elec_path: str) -> np.ndarray:
    elec = np.loadtxt(elec_path, dtype=float)
    if elec.ndim != 2 or elec.shape[1] != 3:
        raise ValueError("Electrode positions file must be N x 3 numeric.")
    if elec.shape[0] < 1:
        raise ValueError("Electrode positions file is empty.")
    return elec


def transform_points(points: np.ndarray, center: np.ndarray, radius: float | None) -> np.ndarray:
    out = points - center[np.newaxis, :]
    if radius is not None:
        out = out / radius
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Recenter (and optionally rescale) scalp mesh + electrode coordinates for spherical spline interpolation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument("scalp_mesh_in", help="Input scalp mesh filename (numeric text).")
    ap.add_argument("electrodes_in", help="Input electrode positions filename (N x 3 numeric text).")

    ap.add_argument(
        "--method",
        choices=["sphere", "centroid"],
        default="sphere",
        help="Transform method: 'sphere' = subtract fitted center and divide by fitted radius (recommended). "
             "'centroid' = subtract centroid only (no scaling). Default: sphere.",
    )
    ap.add_argument(
        "--fit",
        choices=["vertices", "electrodes", "both"],
        default="vertices",
        help="What to fit the sphere/centroid to. Default: vertices.",
    )

    ap.add_argument(
        "--mesh-out",
        default=None,
        help="Output mesh filename. Default: <input_basename>_recentered.txt",
    )
    ap.add_argument(
        "--electrodes-out",
        default=None,
        help="Output electrodes filename. Default: <input_basename>_recentered.txt",
    )
    ap.add_argument(
        "--fmt",
        default="%.10g",
        help="Numeric format for output files (np.savetxt).",
    )

    args = ap.parse_args()

    mesh_in = args.scalp_mesh_in
    elec_in = args.electrodes_in
    method: Method = args.method
    fit: FitTarget = args.fit

    mesh, n_vertices = load_mesh(mesh_in)
    elec = load_electrodes(elec_in)

    vertices = mesh[1 : 1 + n_vertices, :]

    # Choose fit points
    if fit == "vertices":
        fit_points = vertices
    elif fit == "electrodes":
        fit_points = elec
    else:
        fit_points = np.vstack([vertices, elec])

    # Compute transform
    if method == "sphere":
        center, radius = fit_sphere(fit_points)
        scale = radius
    else:
        center = fit_points.mean(axis=0)
        scale = None  # no scaling for centroid method

    # Apply transform to vertices and electrodes
    vertices_t = transform_points(vertices, center=center, radius=scale)
    elec_t = transform_points(elec, center=center, radius=scale)

    # Rebuild mesh (only vertex rows changed)
    mesh_out_arr = mesh.copy()
    mesh_out_arr[1 : 1 + n_vertices, :] = vertices_t

    # Output filenames
    def default_out_name(path: str) -> str:
        base, ext = os.path.splitext(path)
        if ext == "":
            ext = ".txt"
        return f"{base}_recentered{ext}"

    mesh_out = args.mesh_out or default_out_name(mesh_in)
    elec_out = args.electrodes_out or default_out_name(elec_in)

    # Save
    np.savetxt(mesh_out, mesh_out_arr, fmt=args.fmt)
    np.savetxt(elec_out, elec_t, fmt=args.fmt)

    # Print summary + quick sanity checks
    v_norm = np.linalg.norm(vertices_t, axis=1)
    print("Wrote:", mesh_out)
    print("Wrote:", elec_out)
    print("Center:", center)
    print("Radius:", scale if scale is not None else "(no scaling)")
    print("Vertex norm range after transform:", float(v_norm.min()), float(v_norm.max()))
    print("Electrode norm range after transform:", float(np.linalg.norm(elec_t, axis=1).min()),
          float(np.linalg.norm(elec_t, axis=1).max()))


if __name__ == "__main__":
    main()
