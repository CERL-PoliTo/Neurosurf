import argparse
import sys
import subprocess
from enum import Enum
from pathlib import Path
from platform import system
from typing import Optional

from pydantic import (
    BaseModel,
    ValidationError,
    ConfigDict,
    model_validator,
)
from pylsl import resolve_byprop

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # running on <3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Require TOML support (Python 3.11+) or the 'tomli' package.\n"
        ) from e

if sys.version_info < (3, 9):
    raise RuntimeError("This program requires Python 3.9+.")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

CREATION_FLAG = subprocess.CREATE_NEW_CONSOLE if system() == "Windows" else 0
SYS_EXEC = sys.executable
THIS_FOLDER = Path(__file__).resolve().parent
DEFAULT_SLEEP_TIME = 1

LSL_NAME_RAW_DATA = "BrainSurface_raw"
LSL_NAME_BRAIN_DATA = "BrainSurface"
LSL_NAME_FIBERS_DATA = "fibersActivation"
LSL_NAME_SCALP_DATA = "ScalpSurface"

# -----------------------------------------------------------------------------
# Configuration Models
# -----------------------------------------------------------------------------


class SignalOrigin(str, Enum):
    random = "random"
    prerecorded = "prerecorded"
    single = "single"
    eeg = "eeg"
    simulated = "simulated"


class EEGSignalOrigin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_origin: SignalOrigin
    num_channels: Optional[int] = None
    electrode_id: Optional[int] = None
    source_id: Optional[int] = None
    recorded_signal_filepath: Optional[str] = None
    preprocessing_LSL_source: Optional[str] = None

    @model_validator(mode="after")
    def _require_fields_for_origin(self) -> "EEGSignalOrigin":
        """Validate cross-fields for the selected signal origin.

        Raises:
            ValueError: If required fields for the chosen origin are missing.
        """

        s = self.signal_origin
        if s == SignalOrigin.random and self.num_channels is None:
            raise ValueError("'num_channels' is required for origin=random")
        if s == SignalOrigin.single and (
            self.num_channels is None or self.electrode_id is None
        ):
            raise ValueError(
                "'num_channels' and 'electrode_id' are required for origin=single"
            )
        if s == SignalOrigin.prerecorded and not self.recorded_signal_filepath:
            raise ValueError(
                "'recorded_signal_filepath' is required for origin=prerecorded"
            )
        if s == SignalOrigin.simulated and self.source_id is None:
            raise ValueError("'source_id' is required for origin=simulated")
        if s == SignalOrigin.eeg and self.preprocessing_LSL_source is None:
            raise ValueError("'preprocessing_LSL_source' is required for origin=eeg")
        return self


class Brain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_source_localization_enabled: bool
    brain_leadfield: str


class Fiber(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fiber_enabled: bool
    fiber_leadfield: str


class Scalp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scalp_enabled: bool
    scalp_vertices: str
    electrodes_position: str
    cut_below_z: Optional[float] = None


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eeg_signal_origin: EEGSignalOrigin
    brain: Brain
    fiber: Fiber
    scalp: Scalp

    def absolutize_and_check(self, base_dir: Path) -> "AppConfig":
        """Modify the config with absolute paths and file existence checks.

        Args:
            base_dir: Base directory used to resolve relative paths.

        Returns:
            AppConfig: New config instance with absolute paths.

        Raises:
            FileNotFoundError: If a required file does not exist.
        """

        def make_abs(p: Optional[str]) -> Optional[str]:
            if not p:
                return p
            return str((base_dir / p).resolve())

        # Absolutize all paths
        self.brain.brain_leadfield = make_abs(self.brain.brain_leadfield)
        self.fiber.fiber_leadfield = make_abs(self.fiber.fiber_leadfield)
        self.scalp.scalp_vertices = make_abs(self.scalp.scalp_vertices)
        self.scalp.electrodes_position = make_abs(self.scalp.electrodes_position)
        self.eeg_signal_origin.recorded_signal_filepath = make_abs(
            self.eeg_signal_origin.recorded_signal_filepath
        )

        def check_existence(p: Optional[str], label: str):
            """Check existence for mandatory files"""
            if p and not Path(p).is_file():
                raise FileNotFoundError(f"Missing {label} file: {p}")

        if (
            self.brain.brain_source_localization_enabled
            or self.eeg_signal_origin.signal_origin == SignalOrigin.simulated
        ):
            check_existence(self.brain.brain_leadfield, "brain_leadfield")

        if self.fiber.fiber_enabled:
            check_existence(self.fiber.fiber_leadfield, "fiber_leadfield")

        if self.scalp.scalp_enabled:
            check_existence(self.scalp.scalp_vertices, "scalp_vertices")
            check_existence(self.scalp.electrodes_position, "electrodes_position")

        if self.eeg_signal_origin.signal_origin == SignalOrigin.prerecorded:
            check_existence(
                self.eeg_signal_origin.recorded_signal_filepath,
                "recorded_signal_filepath (prerecorded EEG)",
            )

        return self


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _load_config_file(path: Path) -> dict:
    """Load and parse a TOML configuration file.

    Args:
        path: Path to a .toml/.tml file.

    Returns:
        dict: Parsed configuration data.

    Raises:
        ValueError: If the file extension is unsupported.
    """

    if path.suffix.lower() not in {".toml", ".tml"}:
        raise ValueError("Unsupported file format")
    with path.open("rb") as f:
        return tomllib.load(f)


def _get_eeg_signal_args(cfg: AppConfig) -> tuple[str, list[str]]:
    """Build the producer script path and CLI args for the chosen EEG signal origin.

    Args:
        cfg: Validated application configuration.

    Returns:
        tuple[str, list[str]]: Relative script path and argument list.
    """

    eeg = cfg.eeg_signal_origin
    origin = eeg.signal_origin

    if origin == SignalOrigin.random:
        return (
            "eeg_raw_scripts/send_random.py",
            [str(eeg.num_channels), LSL_NAME_RAW_DATA],
        )
    elif origin == SignalOrigin.prerecorded:
        return (
            "eeg_raw_scripts/send_pre_recorded_signal.py",
            [str(eeg.recorded_signal_filepath), LSL_NAME_RAW_DATA],
        )
    elif origin == SignalOrigin.single:
        return (
            "eeg_raw_scripts/send_single_electrode.py",
            [str(eeg.num_channels), LSL_NAME_RAW_DATA, str(eeg.electrode_id)],
        )
    elif origin == SignalOrigin.simulated:
        return (
            "eeg_raw_scripts/send_simulated_volume_to_surface.py",
            [str(cfg.brain.brain_leadfield), str(eeg.source_id), LSL_NAME_RAW_DATA],
        )
    elif origin == SignalOrigin.eeg:
        return (
            "eeg_raw_scripts/eeg_preprocess.py",
            [str(eeg.preprocessing_LSL_source), LSL_NAME_RAW_DATA],
        )
    else:
        raise ValueError(f"Unknown signal origin: {origin}")


def _subprocess_open(script: Path, *args: object) -> subprocess.Popen:
    """Spawn an unbuffered Python subprocess for the given script and args.

    Args:
        script: Python script to run.
        *args: Command-line arguments to pass to the script.

    Returns:
        subprocess.Popen: Handle to the spawned process.
    """

    return subprocess.Popen(
        [SYS_EXEC, "-u", str(script), *map(str, args)],
        creationflags=CREATION_FLAG,
    )


# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cfg_file")
    args = ap.parse_args()

    cfg_file = Path(args.cfg_file)
    cfg_path = (THIS_FOLDER / cfg_file).resolve()

    # Load the configuration file
    raw = _load_config_file(cfg_path)

    # Validate using Pydantic
    try:
        cfg = AppConfig.model_validate(raw)
    except ValidationError as e:
        print("Configuration validation failed:\n")
        print(e)
        sys.exit(1)

    # Make paths absolute and check existence
    try:
        cfg = cfg.absolutize_and_check(THIS_FOLDER)
    except FileNotFoundError as e:
        print(f"{e}")
        sys.exit(1)

    # --- Raw Data Stream Activation -----------------------------------------
    script, script_args = _get_eeg_signal_args(cfg)
    _subprocess_open((THIS_FOLDER / script), *script_args)
    print("Launching EEG data streaming")
    resolve_byprop("name", LSL_NAME_RAW_DATA, timeout=DEFAULT_SLEEP_TIME)

    # --- Brain Stream Activation --------------------------------------------
    if cfg.brain.brain_source_localization_enabled:
        apply_source_path = THIS_FOLDER / "brain_scripts/apply_source_localization.py"
        leadfield_path = cfg.brain.brain_leadfield
        _subprocess_open(
            apply_source_path, leadfield_path, LSL_NAME_RAW_DATA, LSL_NAME_BRAIN_DATA
        )
        print("Launching the source localization algorithm")
        resolve_byprop("name", LSL_NAME_BRAIN_DATA, timeout=DEFAULT_SLEEP_TIME)

    # --- Fiber Activation ---------------------------------------------------
    if cfg.fiber.fiber_enabled and cfg.brain.brain_source_localization_enabled:
        print("Launching fiber streaming...")
        fiber_path_script = THIS_FOLDER / "fibers_scripts/ActivateFiberFromField.py"

        _subprocess_open(
            fiber_path_script,
            cfg.fiber.fiber_leadfield,
            LSL_NAME_BRAIN_DATA,
            LSL_NAME_FIBERS_DATA,
        )
        resolve_byprop("name", LSL_NAME_FIBERS_DATA, timeout=DEFAULT_SLEEP_TIME)

    else:
        print(
            "Fiber streaming not launched. To activate it, enable both "
            "fiber_enabled and brain_source_localization_enabled in the configuration file."
        )

    # --- Scalp Activation ---------------------------------------------------
    if cfg.scalp.scalp_enabled:
        apply_scalp_path = THIS_FOLDER / "scalp_scripts/apply_scalp_interpolation.py"

        scalp_args = [
            cfg.scalp.scalp_vertices,
            cfg.scalp.electrodes_position,
            LSL_NAME_RAW_DATA,
            LSL_NAME_SCALP_DATA,
        ]

        if cfg.scalp.cut_below_z is not None:
            scalp_args.extend(["--cut-below-z", cfg.scalp.cut_below_z])

        _subprocess_open(apply_scalp_path, *scalp_args)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
