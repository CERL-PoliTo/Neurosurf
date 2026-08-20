"""
Spherical spline interpolation for EEG scalp potentials.

This module implements the spherical spline interpolation method described in
"Perrin et al., Electroencephalography and Clinical Neurophysiology, 1989."
"""

import numpy as np
from scipy.special import lpmv

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Truncation order of the Legendre series in the spherical spline kernel.
# For typical EEG caps, 20 is a standard and widely used choice (Perrin et al.).
N_LEGENDRE_TERMS: int = 20


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def get_interpolation_matrix(
    m: float,
    r: np.ndarray,
    electrode_pos: np.ndarray,
) -> np.ndarray:
    """
    Compute the spherical spline interpolation matrix between electrodes and target points.

    Parameters
    ----------
    m : float
        Interpolation order (typically m = 2 or 3 in Perrin's formulation).
    r : ndarray, shape (3, N_points)
        Coordinates of target points where potentials will be interpolated.
    electrode_pos : ndarray, shape (3, N_electrodes)
        Coordinates of electrodes.

    Returns
    -------
    G : ndarray, shape (N_points, N_electrodes)
        Interpolation matrix such that V_points ≈ G @ C (up to an additive constant).
    """
    if not isinstance(r, np.ndarray) or not isinstance(electrode_pos, np.ndarray):
        raise TypeError("r and electrode_pos must be numpy.ndarray instances.")

    if r.shape[0] != 3 or electrode_pos.shape[0] != 3:
        raise ValueError("r and electrode_pos must have shape (3, N).")

    r = r.astype(float, copy=False)
    electrode_pos = electrode_pos.astype(float, copy=False)

    # Normalize to unit sphere
    r_norm = np.linalg.norm(r, axis=0, keepdims=True)
    e_norm = np.linalg.norm(electrode_pos, axis=0, keepdims=True)

    if np.any(r_norm == 0) or np.any(e_norm == 0):
        raise ValueError(
            "Zero-length position vector encountered in r or electrode_pos."
        )

    n1 = r / r_norm
    n2 = electrode_pos / e_norm

    # Cosine of angles between all pairs (dot products on the sphere)
    x = n1.T @ n2  # (N_points, N_electrodes)

    # Numerical safety: keep within [-1, 1]
    x = np.clip(x, -1.0, 1.0)

    # Coefficients for spherical spline kernel
    n = np.arange(1, N_LEGENDRE_TERMS + 1, dtype=float)
    coefs = (2.0 * n + 1.0) / (n * (n + 1.0)) ** m  # shape (N_TERMS,)

    G = np.zeros_like(x, dtype=float)
    for i in range(N_LEGENDRE_TERMS):
        # lpmv(order, degree, x); here order=0
        P_n = lpmv(0, i + 1, x)
        G += coefs[i] * P_n

    G /= 4.0 * np.pi
    return G


def get_interpolated_data(
    interpolation_coefs: np.ndarray,
    G_interpolation: np.ndarray,
) -> np.ndarray:
    """
    Evaluate interpolated potentials from interpolation coefficients.

    Parameters
    ----------
    interpolation_coefs : ndarray, shape (N_electrodes + 1, N_samples)
        Coefficients returned by `get_interpolation_coefs`.
        Last row is the additive constant term c0.
    G_interpolation : ndarray, shape (N_points, N_electrodes)
        Interpolation matrix (e.g. from `get_interpolation_matrix`).

    Returns
    -------
    V_points : ndarray, shape (N_points, N_samples)
        Interpolated potentials at target points.
    """
    if not isinstance(interpolation_coefs, np.ndarray) or not isinstance(
        G_interpolation, np.ndarray
    ):
        raise TypeError(
            "interpolation_coefs and G_interpolation must be numpy.ndarray instances."
        )

    coefs = interpolation_coefs.astype(float, copy=False)
    G = G_interpolation.astype(float, copy=False)

    if coefs.ndim != 2:
        raise ValueError("interpolation_coefs must be 2D (N_electrodes+1, N_samples).")

    c0 = coefs[-1, :]  # (N_samples,)
    c = coefs[:-1, :]  # (N_electrodes, N_samples)

    if G.shape[1] != c.shape[0]:
        raise ValueError(
            f"Shape mismatch: G_interpolation.shape={G.shape}, "
            f"expected second dim={c.shape[0]}."
        )

    V = G @ c  # (N_points, N_samples)
    V += c0[np.newaxis, :]  # broadcast additive constant

    return V


def get_interpolation_coefs(
    G_system: np.ndarray,
    electrode_measurements: np.ndarray,
) -> np.ndarray:
    """
    Solve for spherical spline interpolation coefficients.

    Parameters
    ----------
    G_system : ndarray, shape (N_electrodes + 1, N_electrodes + 1)
        System matrix built by `get_interpolation_system_matrix`.
    electrode_measurements : ndarray, shape (N_electrodes, N_samples)
        Measured electrode potentials.

    Returns
    -------
    coefs : ndarray, shape (N_electrodes + 1, N_samples)
        Interpolation coefficients, last row is c0.
    """
    if not isinstance(G_system, np.ndarray) or not isinstance(
        electrode_measurements, np.ndarray
    ):
        raise TypeError(
            "G_system and electrode_measurements must be numpy.ndarray instances."
        )

    G_sys = G_system.astype(float, copy=False)
    V_e = electrode_measurements.astype(float, copy=False)

    if G_sys.ndim != 2 or G_sys.shape[0] != G_sys.shape[1]:
        raise ValueError("G_system must be a square matrix.")
    if V_e.shape[0] != G_sys.shape[0] - 1:
        raise ValueError(
            "electrode_measurements first dimension must be N_electrodes = G_system.shape[0] - 1."
        )

    # Append zeros for sum(C) = 0 constraint
    rhs = np.vstack([V_e, np.zeros((1, V_e.shape[1]), dtype=float)])

    coefs = np.linalg.solve(G_sys, rhs)
    return coefs


def get_interpolation_system_matrix(
    m: float,
    electrode_pos: np.ndarray,
):
    """
    Build interpolation matrix G and constrained system matrix G_system.

    Parameters
    ----------
    m : float
        Interpolation order.
    electrode_pos : ndarray, shape (3, N_electrodes)
        Electrode positions.

    Returns
    -------
    G : ndarray, shape (N_electrodes, N_electrodes)
        Base interpolation matrix between electrodes.
    G_system : ndarray, shape (N_electrodes + 1, N_electrodes + 1)
        Constrained system matrix:
            [ G    1 ]
            [ 1^T  0 ]
    """
    if not isinstance(electrode_pos, np.ndarray):
        raise TypeError("electrode_pos must be a numpy.ndarray.")

    G = get_interpolation_matrix(m, electrode_pos, electrode_pos)

    n_elec = G.shape[0]
    G_system = np.zeros((n_elec + 1, n_elec + 1), dtype=float)
    G_system[:-1, :-1] = G
    G_system[:-1, -1] = 1.0
    G_system[-1, :-1] = 1.0
    G_system[-1, -1] = 0.0

    return G, G_system


def setup(
    m: float,
    r: np.ndarray,
    electrode_pos: np.ndarray,
):
    """
    Convenience function to precompute all geometry-dependent matrices.

    Parameters
    ----------
    m : float
        Interpolation order.
    r : ndarray, shape (3, N_points)
        Target points (e.g. scalp mesh nodes).
    electrode_pos : ndarray, shape (3, N_electrodes)
        Electrode positions.

    Returns
    -------
    G_system : ndarray, shape (N_electrodes + 1, N_electrodes + 1)
        System matrix for computing coefficients.
    G_electrodes : ndarray, shape (N_electrodes, N_electrodes)
        Interpolation matrix at electrode positions.
    G_scalp : ndarray, shape (N_points, N_electrodes)
        Interpolation matrix at target positions.
    """
    G_electrodes, G_system = get_interpolation_system_matrix(m, electrode_pos)
    G_scalp = get_interpolation_matrix(m, r, electrode_pos)
    return G_system, G_electrodes, G_scalp
