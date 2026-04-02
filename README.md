# Seq-o-Matic 2.5

**Automated Laboratory Platform for Spatial Transcriptomics Sequencing**

Seq-o-Matic is an integrated laboratory automation system for in-situ hybridization (ISH) and barcode sequencing (BARseq) workflows. It orchestrates fluidics exchange, microscope control, and image acquisition to enable fully automated multi-cycle sequencing experiments on tissue samples.

**Author:** Aixin Zhang
**Repository:** [BarseqLab/Seq_o_matics](https://github.com/BarseqLab/Seq_o_matics)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Hardware Requirements](#hardware-requirements)
- [Software Prerequisites](#software-prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Experiment Workflow](#experiment-workflow)
- [For Developers](#for-developers)

---

## Overview

Seq-o-Matic manages three primary subsystems:

1. **Fluidics Exchange** -- Automated delivery of reagents (incorporation buffers, primers, wash solutions, DAPI, etc.) through a peristaltic pump and multi-port selector, with heating stage control for temperature-dependent reactions.

2. **Image Acquisition** -- Automated microscope control including autofocus, image registration/alignment between cycles, tile configuration, and multi-channel z-stack acquisition with max-intensity projection.

3. **Experiment Management** -- Protocol building, real-time logging, experiment metadata tracking, and result upload to network storage.

### Key Benefits

- Reduces manual operational burden, allowing scientists to focus on data analysis
- Minimizes human error in multi-step sequencing protocols
- Provides real-time monitoring with live image display and detailed logging
- Supports flexible experiment design through customizable protocol sequences

---

## Architecture

```
+-------------------------------------------+
|         GUI Layer (front_end/)             |
|  MainWindow | LogWindow | RecipeBuilder   |
|  ExperimentProfile | TissueScanner        |
+-------------------------------------------+
                    |
+-------------------------------------------+
|     System Orchestration (system/)         |
|  FluidicSystem       |  scope             |
|  (pump/selector/     |  (focus/align/     |
|   heater sequences)  |   tile/maxproj)    |
+-------------------------------------------+
                    |
+-------------------------------------------+
|       Device Abstraction (device/)         |
|  IsmatecPumpDevice | ElveflowMux          |
|  heat_stage_group  | KmtronicRelayCh4     |
+-------------------------------------------+
                    |
+-------------------------------------------+
|         Hardware Drivers (driver/)         |
|  Ismatec (serial)  | KmtronicRelay        |
|  PycromanagerCore (microscope via MMCore)  |
+-------------------------------------------+
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

---

## Hardware Requirements

| Device | Model | Interface | Purpose |
|--------|-------|-----------|---------|
| Peristaltic Pump | Ismatec IPC-N series | Serial (COM port) | Reagent delivery |
| Fluid Selector | Elveflow Multiplexer (x2, cascaded) | Serial (COM ports) | Reagent source selection (up to 16 reagents) |
| Heating Stage | Custom (x1-3 stages) | NI DAQ (analog/digital I/O) | Temperature-controlled reactions |
| Relay Controller | KMtronic 4-channel USB | Serial (COM port) | Flow path switching |
| Microscope | Nikon Ti2-E (or compatible) | Micro-Manager | Multi-channel fluorescence imaging |
| Piezo Stage | (Optional) | Via Micro-Manager | Z-stack acquisition |

---

## Software Prerequisites

- **Python** 3.9 - 3.11 (3.12+ not yet tested with all dependencies)
- **Micro-Manager** 2.0 (must be installed and configured for your microscope)
- **NI-DAQmx Driver** (for heating stage control via National Instruments hardware)
- **Operating System:** Windows 10/11 (required for NI-DAQmx and most microscope drivers)

---

## Installation

### Option A: Conda (recommended)

Conda handles all dependencies including compiled libraries (OpenCV, NumPy) in one step:

```bash
# 1. Clone the repository
git clone https://github.com/BarseqLab/Seq_o_matics.git
cd Seq_o_matics

# 2. Create the conda environment (installs Python + all dependencies)
conda env create -f environment.yml

# 3. Activate the environment
conda activate seq-o-matic

# 4. (Optional) Install the package in editable/development mode
pip install -e .
```

### Option B: Pip with virtual environment

```bash
# 1. Clone the repository
git clone https://github.com/BarseqLab/Seq_o_matics.git
cd Seq_o_matics

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install the package and all dependencies
pip install -e .
```

### Option C: Pip from requirements.txt (simplest)

```bash
git clone https://github.com/BarseqLab/Seq_o_matics.git
cd Seq_o_matics
pip install -r requirements.txt
```

### Vendored packages (pycromanager & ndtiff)

`pycromanager` and `ndtiff` are **bundled** in `code/supplementary/package/` and must **not** be installed via pip/conda. The application imports them from this vendored location. Do not run `pip install pycromanager` or `pip install ndtiff` -- it will conflict with the bundled versions.

If you need to update these packages, replace the folders in `code/supplementary/package/` with the new versions.

### Post-install setup

After installing Python dependencies:

1. **Install Micro-Manager 2.0** and configure it for your microscope hardware.
2. **Install the NI-DAQmx driver** from [ni.com](https://www.ni.com/en/support/downloads/drivers/download.ni-daq-mx.html) if using heating stages.
3. **Configure hardware connections** by editing the JSON files in `code/config_file/`. See [Configuration](#configuration) below.

---

## Quick Start

### For Lab Scientists

1. Connect all hardware devices and power them on.
2. Launch Micro-Manager and load your microscope configuration.
3. Open a terminal in the `code/` directory and run:
   ```bash
   # If you used conda:
   conda activate seq-o-matic

   # Launch the application
   python mainwindow.py
   ```
4. In the **Automation** tab:
   - Click **Browse** to select your experiment working directory.
   - Click **Exp** to fill in experiment metadata (brain name, probes, technician, etc.).
   - Click **Config Device** to connect and test all hardware devices.
   - Build your protocol sequence (or use a predefined one).
   - Click **Prime** to fill all fluidics lines with reagent.
   - Click **Start** to begin the automated sequencing run.
5. Monitor progress in the log window. Live images and focus/alignment/tiling plots update in real time.

### For Developers

See the [Project Structure](#project-structure) and [For Developers](#for-developers) sections below.

---

## Project Structure

```
Seq_o_matics_2.5/
  pyproject.toml                     # Python package config (pip install)
  environment.yml                    # Conda environment definition
  requirements.txt                   # Pip dependencies
  README.md                          # This file
  docs/                              # Documentation
    architecture.md                  #   Detailed architecture & data flow
    config_files.md                  #   JSON config file schemas
    reagent_sequences.md             #   Protocol JSON format reference
  code/
    mainwindow.py                    # Application entry point
    constants.py                     # Named constants (replaces magic numbers)
    types_seq.py                     # Shared TypedDicts and type aliases
    logging_config.py                # Python logging setup (TkHandler, file/console)
    config_file/                     # Hardware configuration JSONs
      IsmatecPumpDevice_pump.json    #   Pump serial port and tubing config
      ElveflowMuxDevice_selector.json #  Selector serial ports
      Heat_stage.json                #   DAQ channel assignments
      KMtronic_relay.json            #   Relay serial port
      Fluidics_Reagent_Components.json # Reagent-to-address mapping
      scope.json                     #   Microscope parameters
    device/                          # Hardware device wrappers
      base.py                        #   ABC interfaces (PumpDevice, SelectorDevice, etc.)
      Pump.py                        #   Ismatec pump (implements PumpDevice)
      Selector.py                    #   Elveflow multiplexer (implements SelectorDevice)
      Heatingstage.py                #   Heating stage via NI DAQ (implements HeaterDevice)
      Relay.py                       #   KMtronic relay stub (implements RelayDevice)
    driver/                          # Low-level hardware protocols
      ismatec_ipc.py                 #   Ismatec serial command protocol
      kmtronic_relay.py              #   KMtronic serial command protocol
    front_end/                       # GUI components (Tkinter)
      Widgets.py                     #   Main window coordinator (delegates to panels)
      logwindow.py                   #   LogWindow singleton + notification functions
      experiment_profile.py          #   Experiment metadata dialog
      recipe_builder.py              #   Protocol sequence builder
      tissue_scanner.py              #   Tissue slide scanning & ROI selection
      automation_controller.py       #   Automation state machine (start_sequence, image_auto)
      panels/                        #   Focused UI panel modules
        workspace_panel.py           #     Directory selection, experiment profile
        experiment_config_panel.py   #     Slice/pixel/server/protocol settings
        device_panel.py              #     Device config popup
        fluidics_control_panel.py    #     Prime/fill/wash/start/cancel controls
        imaging_control_panel.py     #     Focus/align/tile/maxprojection controls
        status_panel.py              #     Plot canvases, notes, upload
    system/                          # High-level orchestration
      fluidics_exchange_system.py    #   FluidicSystem facade (device connections)
      fluidics/                      #   Fluidics sub-package
        protocol_loader.py           #     Protocol type -> JSON file mapping
        sequence_runner.py           #     SequenceState enum
      imaging/                       #   Imaging sub-package
        imaging_system.py            #     ImagingSystem facade (composites managers)
        focus.py                     #     FocusManager (z-stack, autofocus)
        alignment.py                 #     AlignmentManager (phase correlation)
        tiling.py                    #     TilingManager (tile grid generation)
        max_projection.py            #     MaxProjectionManager (acquisition + projection)
        position_utils.py            #     Utility functions (position parsing, file I/O)
      image_acquisition_and_analysis_system.py  # Backward-compat shim -> imaging/
    reagent_sequence_file/           # Predefined fluidics protocols (JSON)
      Fluidics_sequence_*.json       #   Protocol definitions
      original_sequence/             #   Backup copies of default protocols
      2IRM_and_2CRM/                 #   Variant protocols (double IRM/CRM)
      750um gasket/                  #   Variant protocols (750um gasket)
    supplementary/                   # Vendored third-party packages (DO NOT pip install)
      package/pycromanager/          #   Micro-Manager Python bridge (bundled, not from PyPI)
      package/ndtiff/                #   ND-TIFF reader (required by pycromanager, bundled)
```

---

## Configuration

All hardware configuration is stored as JSON files in `code/config_file/`. See [docs/config_files.md](docs/config_files.md) for detailed schema documentation.

### Key Configuration Files

- **`scope.json`** -- Microscope name, safe stage positions, exposure times per channel, pixel size, z-direction, alignment channel, max-projection output drive.
- **`IsmatecPumpDevice_pump.json`** -- Serial port, tubing diameter, pump ID.
- **`ElveflowMuxDevice_selector.json`** -- Serial ports for the two cascaded selectors.
- **`Fluidics_Reagent_Components.json`** -- Maps reagent names to selector addresses (1-16).
- **`Heat_stage.json`** -- DAQ device, analog output/input ports, digital output lines per heater.
- **`KMtronic_relay.json`** -- Serial port for the relay controller.

---

## Experiment Workflow

A typical automated sequencing experiment follows this workflow:

```
1. SETUP
   Configure devices -> Set work directory -> Enter experiment metadata
   -> Build or select protocol sequence

2. PRIME
   Fill all fluidics lines with reagent to remove air bubbles

3. FOR EACH CYCLE IN PROTOCOL:

   a) FLUIDICS EXCHANGE (e.g., bcseq01, geneseq02+, HYB, strip)
      Load JSON protocol -> Execute steps sequentially:
        pump: Select reagent source -> Pump specified volume
        heat_device: Heat sample for specified duration (typically 180s)
        wait: Incubate without pumping for specified duration
        stopper: End of sequence

   b) IMAGE ACQUISITION (imagecycleXX)
      Focus:  Autofocus via z-stack sharpness analysis
      Align:  Register to reference cycle (imagecycle00) via phase correlation
      Tile:   Generate tile grid configuration
      MaxProj: Acquire multi-channel z-stacks -> Compute max-intensity projections

4. UPLOAD
   Copy max-projection images to network drive (M:\)
   Upload protocols and data to server via SCP
```

For reagent sequence format documentation, see [docs/reagent_sequences.md](docs/reagent_sequences.md).

---

## For Developers

### Entry Point

The application launches from `code/mainwindow.py`:
1. `Log_window` creates the root Tkinter window and log panels
2. `window_widgets` initializes all UI controls, device connections, and orchestration systems
3. `mainwindow.mainloop()` starts the Tkinter event loop

### Threading Model

The application uses multi-threading to keep the GUI responsive:
- **Main thread**: Tkinter event loop (all GUI updates)
- **Fluidics thread**: `FluidicSystem.startSequence()` runs a `threading.Timer`-based state machine
- **Imaging threads**: Separate threads for focus, alignment, tiling, and max-projection
- **Heating threads**: One thread per heating stage for parallel temperature monitoring

Synchronization uses `threading.Event` objects (`cycle_done_event`, `start_image_event`) for efficient blocking waits, replacing the older polling-loop pattern.

### Logging

The application uses Python's standard `logging` module alongside legacy log methods for comparison:
- **Console**: Structured output `2026-03-30 14:23:05 [INFO] seqomatic.fluidics: message`
- **log.txt**: Timestamped structured entries (via `FileHandler`)
- **GUI panels**: Color-coded messages via custom `TkHandler` (purple for fluidics, blue for scope, red for errors)

Logger hierarchy: `seqomatic.fluidics`, `seqomatic.scope`, `seqomatic.device.pump`, `seqomatic.device.heater`, `seqomatic.device.selector`, `seqomatic.driver.ismatec`.

### Key Classes

**GUI Layer:**

| Class | File | Responsibility |
|-------|------|---------------|
| `window_widgets` | `front_end/Widgets.py` | Main window coordinator (delegates to panels) |
| `LogWindow` | `front_end/logwindow.py` | Singleton log/notification panel |
| `AutomationController` | `front_end/automation_controller.py` | Automation state machine orchestration |
| `WorkspacePanel` | `front_end/panels/workspace_panel.py` | Directory selection, experiment profile |
| `FluidicsControlPanel` | `front_end/panels/fluidics_control_panel.py` | Prime/fill/wash/start/cancel controls |
| `ImagingControlPanel` | `front_end/panels/imaging_control_panel.py` | Focus/align/tile/maxprojection controls |

**System Layer:**

| Class | File | Responsibility |
|-------|------|---------------|
| `FluidicSystem` | `system/fluidics_exchange_system.py` | Device connections facade + sequence execution |
| `load_protocol()` | `system/fluidics/protocol_loader.py` | Protocol type -> JSON file mapping |
| `SequenceState` | `system/fluidics/sequence_runner.py` | Enum: IDLE, RUNNING, CANCELLED, FINISHED |
| `ImagingSystem` | `system/imaging/imaging_system.py` | Imaging facade (composes managers below) |
| `FocusManager` | `system/imaging/focus.py` | Z-stack acquisition, autofocus |
| `AlignmentManager` | `system/imaging/alignment.py` | Phase correlation image registration |
| `TilingManager` | `system/imaging/tiling.py` | Tile grid generation |
| `MaxProjectionManager` | `system/imaging/max_projection.py` | Multi-channel acquisition + max projection |

**Device Layer:**

| Class | File | Responsibility |
|-------|------|---------------|
| `PumpDevice` (ABC) | `device/base.py` | Pump interface |
| `IsmatecPumpDevice` | `device/Pump.py` | Ismatec pump (implements PumpDevice) |
| `ElveflowMux` | `device/Selector.py` | Cascaded selector (implements SelectorDevice) |
| `heat_stage_group` | `device/Heatingstage.py` | Multi-stage heating (implements HeaterDevice) |
| `Ismatec` | `driver/ismatec_ipc.py` | Ismatec pump serial protocol |
| `KmtronicRelay` | `driver/kmtronic_relay.py` | KMtronic relay serial protocol |

### Adding a New Protocol

1. Create a new JSON file in `code/reagent_sequence_file/` following the format in [docs/reagent_sequences.md](docs/reagent_sequences.md).
2. Add an entry to `PROTOCOL_MAP` in `system/fluidics/protocol_loader.py` with a matching lambda condition and filename.
3. Add the protocol option to the recipe builder dropdown if needed.
