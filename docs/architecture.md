# Seq-o-Matic 2.5 -- Architecture Guide

## System Architecture

Seq-o-Matic follows a **four-layer architecture** with clear separation between the user interface, orchestration logic, device abstractions, and hardware drivers.

```
+------------------------------------------------------+
|                   GUI Layer                           |
|                  (front_end/)                         |
|                                                      |
|  mainwindow.py        Entry point, layout            |
|  Widgets.py           Main control panel (auto +     |
|                       manual tabs, all event handlers)|
|  logwindow.py         Log/notification panel         |
|  experiment_profile.py  Experiment metadata dialog   |
|  recipe_builder.py    Protocol sequence builder      |
|  tissue_scanner.py    Slide scanning & ROI selection  |
+------------------------------------------------------+
                         |
                         | Calls methods on system objects
                         v
+------------------------------------------------------+
|            System Orchestration Layer                 |
|                   (system/)                           |
|                                                      |
|  FluidicSystem        Coordinates pump, selector,    |
|                       heater, relay for multi-step   |
|                       fluidics protocols             |
|                                                      |
|  scope                Controls microscope for focus,  |
|                       alignment, tiling, and          |
|                       max-projection acquisition     |
+------------------------------------------------------+
                         |
                         | Calls methods on device wrappers
                         v
+------------------------------------------------------+
|            Device Abstraction Layer                   |
|                   (device/)                           |
|                                                      |
|  IsmatecPumpDevice    Volume-based pump control      |
|  ElveflowMux          Multi-reagent source selection |
|  heat_stage_group     Temperature-controlled heating |
|  KmtronicRelayCh4     Flow path relay switching      |
+------------------------------------------------------+
                         |
                         | Sends serial/DAQ commands
                         v
+------------------------------------------------------+
|              Hardware Driver Layer                    |
|                   (driver/)                           |
|                                                      |
|  Ismatec              Ismatec IPC serial protocol    |
|  KmtronicRelay        KMtronic USB relay protocol    |
|  PycromanagerCore     Micro-Manager bridge           |
|                       (vendored in supplementary/)   |
+------------------------------------------------------+
```

---

## Data Flow

### Fluidics Sequence Execution

```
User clicks "Start"
       |
       v
window_widgets.start_btn_handler()
       |
       v
FluidicSystem.loadSequence(protocol_json)
       |
       v
FluidicSystem.startSequence()
       |
       v
FluidicSystem.runSequence()  <-- recursive Timer-based state machine
       |
       +-- For each step in sequence:
       |     |
       |     +-- "pump" device:
       |     |     ElveflowMux.set_path(reagent)
       |     |     IsmatecPumpDevice.pumpVolume(volume, rate)
       |     |     [wait for pump to finish]
       |     |
       |     +-- "heat_device":
       |     |     heat_stage_group.heat_for_3min()
       |     |     [parallel threads per heater, ~180s]
       |     |
       |     +-- "wait":
       |     |     [sleep for specified duration]
       |     |
       |     +-- "stopper":
       |           [sequence complete]
       |
       v
FluidicSystem.sequenceStatus = -2  (finished)
```

### Sequence State Machine

The `FluidicSystem.runSequence()` method uses a recursive `threading.Timer` pattern to avoid blocking the GUI thread:

```
Status codes:
  sequenceStatus =  0  -> IDLE (not running)
  sequenceStatus =  1  -> RUNNING (sequence in progress)
  sequenceStatus = -1  -> CANCELLED (user pressed cancel)
  sequenceStatus = -2  -> FINISHED (sequence completed normally)
```

Each call to `runSequence()`:
1. Checks if cancelled (`sequenceStatus == -1`)
2. Checks if pump is still running from previous step
3. Executes the current step based on device type
4. Increments `sequenceIndex`
5. Schedules next `runSequence()` call via `threading.Timer(3, self.runSequence)`

### Imaging Pipeline

```
image_auto() -- called after each fluidics cycle completes
       |
       +-- 1. do_focus_thread()
       |        scope.focus_image()
       |        -> Acquire z-stack at each position
       |        -> Calculate sharpness per z-plane
       |        -> Select best focus plane
       |        -> Save as dicfocuscycleXX/
       |
       +-- 2. align_and_draw_thread()
       |        scope.do_alignment()
       |        -> Load current + reference (cycle00) images
       |        -> Phase correlation (imregcorr) per position
       |        -> Compute XY shifts
       |        -> Sanity check (reject large shifts/tilts)
       |        -> Write updated position file
       |
       +-- 3. tile_and_draw_thread()
       |        scope.make_tile()
       |        -> Load aligned positions
       |        -> Calculate tile grid with overlap
       |        -> Write tile configuration
       |
       +-- 4. maxprojection_thread()
                scope.image_and_maxprojection()
                -> For each tile position:
                     Acquire z-stack in all channels
                     Compute max-intensity projection per channel
                     Save as TIFF
                -> Copy to network drive (M:\)
```

### Image Registration (Phase Correlation)

The `imregcorr()` function in the scope module implements sub-pixel image registration:

1. Apply Blackman window to both images (reduces edge artifacts)
2. Compute 2D FFT of both images
3. Calculate cross-power spectrum
4. Inverse FFT to get correlation surface
5. Find peak location -> integer pixel shift
6. Refine to sub-pixel accuracy via centroid of peak neighborhood

---

## Threading Model

```
Main Thread (Tkinter event loop)
  |
  +-- Fluidics Thread
  |     FluidicSystem.startSequence()
  |     -> Recursive threading.Timer chain
  |     -> Sets cycle_done flag when complete
  |
  +-- Focus Thread
  |     scope.focus_image()
  |     -> Sets focus_status flag when complete
  |
  +-- Alignment Thread
  |     scope.do_alignment()
  |     -> Uses ThreadPoolExecutor for parallel position processing
  |     -> Sets alignment_status flag when complete
  |
  +-- Tiling Thread
  |     scope.make_tile()
  |     -> Sets tile_status flag when complete
  |
  +-- Max-Projection Thread
  |     scope.image_and_maxprojection()
  |     -> Sets maxprojection_status flag when complete
  |
  +-- Heating Threads (1 per stage)
        heat_stage_group.heat_for_3min()
        -> Monitors temperature via DAQ analog input
        -> Reports to result_queue
```

**Synchronization:** The automation controller in `window_widgets.start_sequence()` polls status flags in `while` loops with `time.sleep(2)` to wait for each step to complete before starting the next.

---

## Configuration Loading

At startup:
1. `FluidicSystem.__init__()` loads device configs from `config_file/`:
   - `IsmatecPumpDevice_pump.json` -> Pump connection parameters
   - `ElveflowMuxDevice_selector.json` -> Selector serial ports
   - `Heat_stage.json` -> DAQ channel assignments
   - `KMtronic_relay.json` -> Relay serial port
   - `Fluidics_Reagent_Components.json` -> Reagent-to-address mapping
2. `scope.__init__()` loads `scope.json` -> Microscope parameters
3. Protocol JSONs from `reagent_sequence_file/` are loaded at runtime when a sequence is started

---

## File Organization During an Experiment

When an experiment runs, the working directory accumulates:

```
experiment_folder/
  experiment_detail.txt        # Metadata (brain, probes, technician, etc.)
  protocol.csv                 # The protocol sequence used
  reagents.csv                 # Reagent usage log
  log.txt                      # Runtime log
  auto.csv                     # Tissue ROI coordinates (from scanner)
  *.pos                        # Stage position files
  dicfocuscycle00/             # Reference focus images
  dicfocuscycleXX/             # Focus images per cycle
  imagecycle00/                # Reference alignment images
  imagecycleXX/                # Aligned images per cycle
  maxprojectioncycleXX/        # Max-projection output per cycle
  Fluidics_sequence_*.json     # Copies of protocols used
```
