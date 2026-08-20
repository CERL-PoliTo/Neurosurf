# Neurosurf

Neurosurf is a research framework for interactive visualization of EEG source imaging results.

The project combines a Python-based data processing pipeline with a Unity visualization environment. The Python module can acquire or generate EEG data, perform preprocessing and source localization, and stream the resulting quantities through the [Lab Streaming Layer (LSL)](https://labstreaminglayer.readthedocs.io/) protocol. The Unity application receives these streams and provides an interactive visualization of activity on the scalp, brain, and white-matter fiber tracts.

The framework supports multiple EEG source imaging methods and is designed to accommodate custom processing pipelines and forward/inverse models. The visualization can be used either directly from the Unity Editor with keyboard and mouse controls or in virtual reality.

## Requirements

Before installing Neurosurf, make sure the following software is available:

* Python 3.11 or later
* [uv](https://docs.astral.sh/uv/getting-started/installation/)
* Unity Editor `6000.0.58f2`

Python dependencies are managed through `uv` and are installed automatically when running the pipeline.

## Installation

Open the repository folder as a project in Unity using Unity Editor version `6000.0.58f2`.

On the first launch, Unity may require additional time to import the project and download its dependencies.

Before running the application for the first time, it is recommended to download the sample assets from the Unity menu:

```text
Setup → Download Assets
```

Then open the Neurosurf scene located in:

```text
Assets/Scenes/
```

## Running Neurosurf

Neurosurf consists of two components that need to be running at the same time:

1. the Python data pipeline;
2. the Unity visualization.

### Python pipeline

From the `BrainScripts/` directory, run:

```bash
uv run PipelineStarter.py <configuration-file.toml>
```

For example:

```bash
uv run PipelineStarter.py configuration_simulated.toml
```

Alternatively, on Windows, the pipeline can be started by double-clicking:

```text
run.bat
```

The TOML configuration file determines the input data source, processing pipeline, source imaging method, model files, and output streams used by the application.

### Unity visualization

After starting the Python pipeline:

1. open the Neurosurf scene in Unity;
2. press **Play** in the Unity Editor.

The application will connect to the corresponding LSL streams and visualize the incoming data.

## Desktop controls

The application can be controlled using keyboard and mouse when running from the Unity Editor.

| Input                   | Action                                            |
| ----------------------- | ------------------------------------------------- |
| `W` / `A` / `S` / `D`   | Move horizontally                                 |
| `Q` / `E`               | Move vertically                                   |
| `←` / `→`               | Rotate the head model                             |
| `1` / `2` / `3` / `4`   | Enable or disable scalp, skull, brain, and fibers |
| `I` / `J`               | Increase / decrease scalp transparency            |
| `O` / `K`               | Increase / decrease skull transparency            |
| `P` / `L`               | Increase / decrease brain transparency            |
| `C`                     | Change colormap                                   |
| Hold right mouse button | Change camera orientation                         |

## VR controls

### Controllers

| Input                 | Action                           |
| --------------------- | -------------------------------- |
| Trigger               | Interact with the user interface |
| Grip                  | Interact with the head model     |
| Two-hand grip         | Scale the head model             |
| Controller buttons    | Change colormap                  |
| Left thumbstick       | Move                             |
| Right thumbstick up   | Teleport                         |
| Right thumbstick down | Rotate by 180°                   |

### Hand tracking

| Gesture          | Action                                         |
| ---------------- | ---------------------------------------------- |
| Index pinch      | Interact with the user interface or head model |
| Two-handed pinch | Scale the head model                           |

## Configuration files

The behavior of the Python pipeline is controlled through TOML configuration files passed to `PipelineStarter.py`.

Different configurations can be used to select, for example:

* the EEG data source;
* preprocessing operations;
* the source imaging method;
* lead-field matrices and anatomical models;
* the quantities streamed to Unity.

File paths and processing parameters can therefore be changed without modifying the Python source code.

## Project structure

The main components of the repository are:

```text
BrainScripts/
    Python data processing and EEG source imaging pipeline

Assets/
    Unity assets, scripts, scenes, shaders, and visualization components

physical_models/
    Anatomical models, lead fields, and related model data
```

The exact set of available files may depend on the sample assets installed through the Unity `Setup` menu.

## Communication between modules

The Python and Unity components communicate through [Lab Streaming Layer (LSL)](https://labstreaminglayer.readthedocs.io/).

This separation allows the data processing and visualization modules to run independently and makes it possible to replace or extend the EEG processing pipeline while keeping the visualization interface unchanged.
