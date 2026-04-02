"""
Main ImagingSystem class that composes FocusManager, AlignmentManager,
TilingManager, and MaxProjectionManager into a unified microscope control interface.

This is the refactored equivalent of the original ``scope`` class, preserving
the same public method API for backward compatibility.
"""
import json
import os
import threading

import numpy as np
import pandas as pd
from pycromanager import Core

from front_end.logwindow import update_error
from system.imaging.alignment import AlignmentManager
from system.imaging.focus import FocusManager
from system.imaging.max_projection import MaxProjectionManager
from system.imaging.position_utils import (
    scope_constant, get_pos_data, get_time, get_file_name as _get_file_name,
)
from system.imaging.tiling import TilingManager


class ImagingSystem:
    """Main microscope control and image analysis orchestrator.

    Manages the full sequencing imaging pipeline: focus finding, cycle-to-cycle
    alignment via phase correlation, tile grid generation, multi-channel z-stack
    acquisition with piezo or stage-based focusing, max-intensity projection,
    and data transfer to remote servers. Communicates with Micro-Manager Core
    via pycromanager for hardware control.

    This class composes dedicated manager objects for each pipeline stage:
    - FocusManager: z-stack acquisition and autofocus
    - AlignmentManager: cycle-to-cycle image registration
    - TilingManager: tile grid generation
    - MaxProjectionManager: max-projection and data transfer
    """

    def __init__(self, cfg, pos_path, slice_per_slide, server, mock_align, fine_align, system_path):
        """Initialize the scope controller with hardware configuration and experiment parameters.

        Args:
            cfg: List containing a configuration dictionary with keys for hardware settings
                 (pixel_size, imwidth, overlap, piezo, exposure times, stage directions, etc.).
            pos_path: Base directory path for position files, logs, and image data.
            slice_per_slide: List of integers specifying the number of tissue slices per slide.
            server: SSH address of the Linux server for data transfer (e.g., 'user@host').
            mock_align: Flag (1 = skip alignment computation, use identity transform).
            fine_align: Flag for enabling fine alignment mode.
            system_path: Path to the system code directory.
        """
        self.system_path = system_path
        self.scope_cfg = cfg
        self.core = Core()
        self.pos_path = pos_path
        self.slicePerSlide = slice_per_slide
        self.focus_status = 0
        self.alignment_status = 0
        self.maketiles_status = 0
        self.max_projection_status = 0
        self.maxprojection_name = ''
        self.cancel_process = 0
        self.live_plot = 0
        self.focus_bad = 0
        self.linux_server = server
        self.mock_align = mock_align
        self.ZDrive_safe_pos = self.scope_cfg[0]["ZDrive_safe_pos"]
        self.XYStage_fluidics_safe_pos = self.scope_cfg[0]["XYStage_fluidics_safe_pos"]
        self.piezo = self.scope_cfg[0]["piezo"]
        self.XYStage_image_safe_pos = self.scope_cfg[0]["XYStage_image_safe_pos"]
        self.scope_exposure_time_dict = self.scope_cfg[0]["scope_exposure_time_dict"]
        self.z_dir = self.scope_cfg[0]["z_dir"]
        self.stage_x_dir = self.scope_cfg[0]["stage_x_dir"]
        self.stage_y_dir = self.scope_cfg[0]["stage_y_dir"]
        self.pixelsize = self.scope_cfg[0]["pixel_size"]
        self.imwidth = self.scope_cfg[0]["imwidth"]
        self.overlap = self.scope_cfg[0]["overlap"]
        self.maxprojection_drive = self.scope_cfg[0]["maxproject_drive"]
        self.fine_align = fine_align
        self.gene_target_channel = self.scope_cfg[0]["geneseq_focus_target_channel"]
        self.hyb_target_channel = self.scope_cfg[0]["Hyb_focus_target_channel"]
        self.align_channel = self.scope_cfg[0]["align_channel"]
        self.thread_limiter = threading.Semaphore(10)

        if self.piezo == 1:
            self.stack_num_focus = round(
                abs(scope_constant.piezo_focus_end_pos - scope_constant.piezo_focus_start_pos) / scope_constant.piezo_step)
            self.stack_num_maxpro = round(
                abs(scope_constant.piezo_maxpro_start_pos - scope_constant.piezo_maxpro_end_pos) / scope_constant.piezo_step)
        else:
            self.stack_num_focus = round(
                abs(scope_constant.scope_focus_end_pos - scope_constant.scope_focus_start_pos) / scope_constant.scope_step)
            self.stack_num_maxpro = round(
                abs(scope_constant.scope_start_pos - scope_constant.scope_end_pos) / scope_constant.scope_step)

        # Compose manager objects
        self._focus_mgr = FocusManager(self)
        self._alignment_mgr = AlignmentManager(self)
        self._tiling_mgr = TilingManager(self)
        self._maxprojection_mgr = MaxProjectionManager(self)

    # ------------------------------------------------------------------
    # Utility / lifecycle methods (kept directly on ImagingSystem)
    # ------------------------------------------------------------------

    def move_to_fluidics(self):
        """Move the stage to the safe fluidics position (currently a no-op placeholder)."""
        pass

    def move_to_image(self):
        """Move the stage to the safe imaging position (currently a no-op placeholder)."""
        pass

    def check_cycle00(self):
        """Validate that cycle00.pos has the expected number of positions matching slice_per_slide.

        Returns:
            1 if the position count is correct, 0 otherwise (also displays an error).
        """
        with open(os.path.join(self.pos_path, "cycle00.pos")) as f:
            d = json.load(f)
        if self.piezo == 1:
            focus_poslist = pd.DataFrame(
                [get_pos_data(item, self.piezo) for item in d['map']['StagePositions']['array']])[
                ['position', 'x', 'y', 'z', 'piezo']]
        else:
            focus_poslist = pd.DataFrame(
                [get_pos_data(item, self.piezo) for item in d['map']['StagePositions']['array']])[
                ['position', 'x', 'y', 'z']]

        if len(focus_poslist) != sum(self.slicePerSlide) * 4:
            print(len(focus_poslist))
            print(sum(self.slicePerSlide) * 4)
            update_error("Slice per slide is not consistent with number of FOV!")
            check_file = 0
        else:
            check_file = 1
        return check_file

    def get_pixel(self, ind, dataset):
        """Read a single image from a dataset using the given index parameters."""
        pixels = dataset.read_image(**ind)
        return pixels

    def write_log(self, txt):
        """Append a text message to the experiment log file (log.txt)."""
        f = open(os.path.join(self.pos_path, "log.txt"), "a")
        f.write(txt)
        f.close()

    def get_file_name(self, path, kind):
        """Return a list of filenames in the given directory that end with the specified extension.

        Args:
            path: Directory to search.
            kind: File extension filter (e.g., '.tif').

        Returns:
            List of matching filenames.
        """
        return _get_file_name(path, kind)

    def pos_to_csv(self, cycle):
        """Convert a Micro-Manager .pos JSON position file to a CSV file.

        Reads the stage positions from the .pos file, extracts x, y, z (and piezo
        if present), and writes the result as a CSV alongside the .pos file.

        Args:
            cycle: Cycle name string. 'imagecycle00' maps to 'cycle00.pos/csv'.

        Returns:
            DataFrame containing the position list.
        """
        if cycle == "imagecycle00":
            with open(os.path.join(self.pos_path, "cycle00.pos")) as f:
                d = json.load(f)
        else:
            with open(os.path.join(self.pos_path, cycle + ".pos")) as f:
                d = json.load(f)
        if self.piezo == 1:
            poslist = pd.DataFrame(
                [get_pos_data(item, self.piezo) for item in d['map']['StagePositions']['array']])[
                ['position', 'x', 'y', 'z', 'piezo']]
        else:
            poslist = pd.DataFrame(
                [get_pos_data(item, self.piezo) for item in d['map']['StagePositions']['array']])[
                ['position', 'x', 'y', 'z']]
        if cycle == "imagecycle00":
            poslist.to_csv(os.path.join(self.pos_path, "cycle00.csv"), index=False)
        else:
            poslist.to_csv(os.path.join(self.pos_path, cycle + ".csv"), index=False)
        return poslist

    # ------------------------------------------------------------------
    # Delegated Focus methods
    # ------------------------------------------------------------------

    def get_sharpness(self, f, sharpen):
        """Compute an image sharpness metric using gradient magnitude after median blur and sharpening."""
        return self._focus_mgr.get_sharpness(f, sharpen)

    def calculate_z_stack(self, start_pos, end_pos):
        """Calculate piezo z-stack positions centered on the piezo middle position."""
        return self._focus_mgr.calculate_z_stack(start_pos, end_pos)

    def create_piezo_event(self, channel, start_pos, end_pos):
        """Build a list of pycromanager acquisition events for a piezo-driven multi-channel z-stack."""
        return self._focus_mgr.create_piezo_event(channel, start_pos, end_pos)

    def calculate_z_stack_without_piezo(self, middle, start_pos, end_pos):
        """Calculate z-stack positions using the main ZDrive stage (no piezo)."""
        return self._focus_mgr.calculate_z_stack_without_piezo(middle, start_pos, end_pos)

    def create_scope_event(self, channel, pos, start_pos, end_pos, middle_pos):
        """Build acquisition events for a stage-driven (non-piezo) multi-channel z-stack."""
        return self._focus_mgr.create_scope_event(channel, pos, start_pos, end_pos, middle_pos)

    def image_with_piezo(self, path, pos, piezo_event, x, y, z, piezo_z):
        """Move to the specified XYZ + piezo position and acquire a z-stack."""
        return self._focus_mgr.image_with_piezo(path, pos, piezo_event, x, y, z, piezo_z)

    def image_with_scope(self, path, pos, piezo_event, x, y):
        """Acquire images using stage-based z-drive (no piezo)."""
        return self._focus_mgr.image_with_scope(path, pos, piezo_event, x, y)

    def find_focus_plane(self, pos):
        """Find the best-focused z-plane for a given position by maximizing sharpness."""
        return self._focus_mgr.find_focus_plane(pos)

    def focus_image(self, cycle, poslist):
        """Acquire focus z-stacks at all positions and determine the optimal focus plane."""
        return self._focus_mgr.focus_image(cycle, poslist)

    # ------------------------------------------------------------------
    # Delegated Alignment methods
    # ------------------------------------------------------------------

    def do_alignment(self, cycle):
        """Perform image registration (alignment) between cycle00 and the current cycle."""
        return self._alignment_mgr.do_alignment(cycle)

    def calculate_shift_singlethread(self, i):
        """Compute the XY translation offset for a single position index."""
        return self._alignment_mgr.calculate_shift_singlethread(i)

    def calculate_shift(self):
        """Run threaded phase-correlation alignment for all positions."""
        return self._alignment_mgr.calculate_shift()

    def update_regoffsetfile(self):
        """Apply pooled alignment offsets to position CSV and JSON files."""
        return self._alignment_mgr.update_regoffsetfile()

    def createBlackmanWindow(self, windowSize):
        """Create a 2D Blackman-Harris window for FFT-based registration."""
        return self._alignment_mgr.createBlackmanWindow(windowSize)

    def machineEpsilon(self, func=float):
        """Compute the machine epsilon for a given numeric type."""
        return self._alignment_mgr.machineEpsilon(func)

    def imregcorr(self, moving, fixed):
        """Compute sub-pixel XY translation between two images using phase correlation."""
        return self._alignment_mgr.imregcorr(moving, fixed)

    def sanity_check_alignment(self):
        """Pool alignment offsets per slide and check for excessive tilt."""
        return self._alignment_mgr.sanity_check_alignment()

    # ------------------------------------------------------------------
    # Delegated Tiling methods
    # ------------------------------------------------------------------

    def make_tile(self, cycle):
        """Generate the imaging tile grid after alignment completes."""
        return self._tiling_mgr.make_tile(cycle)

    def load_achor_regpos(self):
        """Load the registered offset position file for the current cycle."""
        return self._tiling_mgr.load_achor_regpos()

    def count_tiles(self):
        """Load cycle00 CSV to count tile positions."""
        return self._tiling_mgr.count_tiles()

    def createtiles(self):
        """Generate tiled imaging positions from registered anchor points."""
        return self._tiling_mgr.createtiles()

    def fix_Posinfo(self):
        """Remap tile position naming to match expected row/column convention."""
        return self._tiling_mgr.fix_Posinfo()

    # ------------------------------------------------------------------
    # Delegated MaxProjection methods
    # ------------------------------------------------------------------

    def image_and_maxprojection(self, cycle):
        """Acquire multi-channel z-stacks for all tiles and compute max-intensity projections."""
        return self._maxprojection_mgr.image_and_maxprojection(cycle)

    def create_max_projection_folder(self):
        """Create local and max-projection output directories for the current cycle."""
        return self._maxprojection_mgr.create_max_projection_folder()

    def Assign_image_channel(self):
        """Set the imaging channel list based on the current cycle type."""
        return self._maxprojection_mgr.Assign_image_channel()

    def start_max_imgage_cycle(self):
        """Start the max-projection imaging cycle."""
        return self._maxprojection_mgr.start_max_imgage_cycle()

    def maxprojection_image_cycle(self):
        """Execute the full imaging loop: acquire z-stacks and compute max-projections."""
        return self._maxprojection_mgr.maxprojection_image_cycle()

    def process_scope_image(self, pos):
        """Process a single acquired tile: compute max-projection and update live view."""
        return self._maxprojection_mgr.process_scope_image(pos)

    def maxprojection(self, pos):
        """Compute max-intensity projection across z-slices for each channel."""
        return self._maxprojection_mgr.maxprojection(pos)

    def send_protocol(self, pos_path):
        """Transfer protocol files to the remote server via SCP."""
        return self._maxprojection_mgr.send_protocol(pos_path)

    def send_to_server(self, pos_path):
        """Transfer the max-projection image directory to the remote Linux server."""
        return self._maxprojection_mgr.send_to_server(pos_path)

    def live_view(self, img):
        """Generate a false-color composite image from 4 fluorescence channels."""
        return self._maxprojection_mgr.live_view(img)

    def check_transfer_complete(self, disk):
        """Verify that all expected max-projection TIFF files were written to disk."""
        return self._maxprojection_mgr.check_transfer_complete(disk)
