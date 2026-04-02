"""
Focus management for microscope imaging.

Handles z-stack acquisition, sharpness-based autofocus, and piezo/stage
event generation for the imaging pipeline.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait

import cv2
import numpy as np
import pandas as pd
import skimage
import tifffile
from pycromanager import Acquisition

from front_end.logwindow import (
    update_error, add_highlight_from_scope,
    update_process_bar, update_process_label,
)
from system.imaging.position_utils import (
    scope_constant, get_time, clean_space, copy_dic, save_offset_and_json,
)


class FocusManager:
    """Manages focus-finding operations including z-stack acquisition and sharpness analysis.

    Handles piezo and stage-based z-stack generation, image acquisition at focus
    positions, and determination of optimal focus planes via sharpness metrics.
    """

    def __init__(self, parent):
        """Initialize the FocusManager with a reference to the parent ImagingSystem.

        Args:
            parent: The parent ImagingSystem instance providing core, config, and path state.
        """
        self._parent = parent

    def get_sharpness(self, f, sharpen):
        """Compute an image sharpness metric using gradient magnitude after median blur and sharpening.

        Applies a 3x3 median blur, convolves with the sharpening kernel, then computes
        the average gradient magnitude as a focus quality score.

        Args:
            f: 2D image array.
            sharpen: Sharpening convolution kernel.

        Returns:
            Average gradient magnitude (higher = sharper/more in focus).
        """
        img = np.array(f)
        img_filter = cv2.medianBlur(img, 3)
        sharpen_img = cv2.filter2D(img_filter, -1, sharpen)
        gy, gx = np.gradient(sharpen_img)
        gnorm = np.sqrt(gx ** 2 + gy ** 2)
        return np.average(gnorm)

    def calculate_z_stack(self, start_pos, end_pos):
        """Calculate piezo z-stack positions centered on the piezo middle position from the cycle CSV.

        Args:
            start_pos: Relative start offset from the piezo middle position.
            end_pos: Relative end offset from the piezo middle position.

        Returns:
            NumPy array of absolute piezo positions for the z-stack sweep.
        """
        p = self._parent
        df = pd.read_csv(os.path.join(p.pos_path, p.cycle + ".csv"))
        p.piezo_middle_pos = df['piezo'][0]
        piezo_event_pos = np.arange(p.piezo_middle_pos + start_pos, p.piezo_middle_pos + end_pos,
                                    scope_constant.piezo_step)
        return piezo_event_pos

    def create_piezo_event(self, channel, start_pos, end_pos):
        """Build a list of pycromanager acquisition events for a piezo-driven multi-channel z-stack.

        Each event specifies a channel, z-slice index, exposure time, and piezo z position.

        Args:
            channel: List of channel names (e.g., ['G', 'T', 'A', 'C']).
            start_pos: Relative start offset for z-stack.
            end_pos: Relative end offset for z-stack.

        Returns:
            List of event dictionaries compatible with pycromanager Acquisition.acquire().
        """
        p = self._parent
        p.piezo_event_pos = self.calculate_z_stack(start_pos, end_pos)
        piezo_event = []
        p.channel=[]
        for c in channel:
            for z in range(0, len(p.piezo_event_pos)):
                piezo_event.append({'axes': {'channel': c, 'z': z},
                                    'config_group': ['Channel', c],
                                    'exposure': p.scope_exposure_time_dict.get(c),
                                    'z': p.piezo_event_pos[z]})
                p.channel.append(c)

        return piezo_event

    def calculate_z_stack_without_piezo(self, middle, start_pos, end_pos):
        """Calculate z-stack positions using the main ZDrive stage (no piezo).

        Args:
            middle: Absolute middle z position.
            start_pos: Relative start offset.
            end_pos: Relative end offset.

        Returns:
            NumPy array of absolute z positions for the stage-driven z-stack.
        """
        scope_event_pos = np.arange(middle + start_pos, middle + end_pos,
                                    scope_constant.scope_step)
        return scope_event_pos

    def create_scope_event(self, channel, pos, start_pos, end_pos, middle_pos):
        """Build acquisition events for a stage-driven (non-piezo) multi-channel z-stack.

        Args:
            channel: List of channel names.
            pos: Position identifier string.
            start_pos: Relative start offset for z-stack.
            end_pos: Relative end offset for z-stack.
            middle_pos: Absolute middle z position of the ZDrive.

        Returns:
            List of event dictionaries for pycromanager Acquisition.acquire().
        """
        p = self._parent
        p.scope_event_pos = self.calculate_z_stack_without_piezo(middle_pos, start_pos, end_pos)
        print(p.scope_event_pos)
        scope_event = []
        for c in channel:
            for z in range(0, len(p.scope_event_pos)):
                scope_event.append({'axes': {'channel': c, 'z': z,'Pos':pos},
                                    'config_group': ['Channel', c],
                                    'exposure': p.scope_exposure_time_dict.get(c),
                                    'z': p.scope_event_pos[z]})
        return scope_event

    def image_with_piezo(self, path, pos, piezo_event, x, y, z, piezo_z):
        """Move to the specified XYZ + piezo position and acquire a z-stack using piezo events.

        Moves the XY stage, ZDrive, and piezo to their target positions, then runs
        the acquisition. Resets the piezo to 200 um after completion.

        Args:
            path: Directory to save the acquired images.
            pos: Position name for the acquisition.
            piezo_event: List of piezo acquisition event dictionaries.
            x: Target X stage position in micrometers.
            y: Target Y stage position in micrometers.
            z: Target ZDrive position in micrometers.
            piezo_z: Initial piezo position in micrometers.
        """
        p = self._parent
        p.core.set_xy_position(x, y)
        p.core.wait_for_device("XYStage")
        txt = get_time() + "XYStage ready"+"\n"
        p.write_log(txt)
        p.core.set_position("ZDrive", z)
        p.core.wait_for_device("ZDrive")
        txt = get_time() + "ZDrive ready"+"\n"
        p.write_log(txt)
        p.core.set_position("DA Z Stage", piezo_z)
        p.core.wait_for_device("DA Z Stage")
        txt = get_time() + "DA Z Stage"+"\n"
        p.write_log(txt)
        txt = get_time() + p.cycle + ' scope start acq.acquire ' + pos + "\n"
        p.write_log(txt)
        add_highlight_from_scope(txt)
        with Acquisition(directory=path, name=pos,
                         show_display=False) as acq:
            acq.acquire(piezo_event)
            acq.mark_finished()
        p.core.stop_stage_sequence('DA Z Stage')
        p.core.wait_for_device("DA Z Stage")
        p.core.set_position("DA Z Stage", 200)
        txt = get_time() + "Piezo reset"+"\n"
        p.write_log(txt)

    def image_with_scope(self, path, pos, piezo_event, x, y):
        """Acquire images using stage-based z-drive (no piezo). Currently a placeholder."""
        pass

    def find_focus_plane(self, pos):
        """Find the best-focused z-plane for a given position by maximizing sharpness.

        Reads the z-stack from the focus acquisition, computes sharpness for each slice,
        selects the sharpest plane, saves the best-focus image as a TIFF, and records
        the corresponding piezo z position.

        Args:
            pos: Position name string (e.g., 'Pos0').
        """
        p = self._parent
        img = tifffile.imread(os.path.join(p.pos_path, "focus" + p.cycle, pos+"_1", pos + "_NDTiffStack.tif"))
        if p.focus_channel[0]==p.focus_channel[1]:
            focusimg =img
            display_img = img
        else:
            img_reshaped_array = img.reshape(80, p.imwidth, p.imwidth)
            display_img=[img_reshaped_array[i] for i in range(len(p.channel)) if p.channel[i] == p.align_channel]
            focusimg=[img_reshaped_array[i] for i in range(len(p.channel)) if p.channel[i] == p.target_channel]
        sharpness = [self.get_sharpness(i[800:2400, 800:2400], scope_constant.sharpen1) for i in focusimg]
        max_index = np.argmax(sharpness)
        z_name = pos + ".tif"
        im = display_img[max_index]
        skimage.io.imsave(z_name, im, photometric='minisblack')
        dict = {pos: p.piezo_event_pos[max_index]}
        p.z_new_ls.update(dict)
        txt = get_time() + p.cycle + " Position " + str(pos) + ' is_finished \n'
        p.write_log(txt)
        add_highlight_from_scope(txt)

    def focus_image(self, cycle, poslist):
        """Acquire focus z-stacks at all positions and determine the optimal focus plane.

        For each position in poslist, moves the stage and acquires a piezo z-stack.
        Then finds the sharpest z-plane per position using threaded processing,
        saves z-offset corrections, and checks for extreme focus changes.

        Args:
            cycle: Cycle name string (e.g., 'cycle01', 'hyb01').
            poslist: DataFrame with columns 'position', 'x', 'y', 'z' (and optionally 'piezo').

        Returns:
            Array of z-shift differences, or 0 if focusing failed.
        """
        p = self._parent
        p.cancel_process = 0
        p.cycle = cycle

        if "hyb" in p.cycle:
            p.focus_channel = [p.align_channel]+[p.hyb_target_channel]
            p.target_channel = p.hyb_target_channel

        else:
            p.focus_channel = [p.align_channel]+[p.gene_target_channel]
            p.target_channel = p.gene_target_channel
        print(p.focus_channel)
        p.z_new_ls = {}
        p.piezo_event = self.create_piezo_event(p.focus_channel, scope_constant.piezo_focus_start_pos,
                                                   scope_constant.piezo_focus_end_pos)
        threads = []
        focus_dir = os.path.join(p.pos_path, "focus" + p.cycle)
        clean_space(focus_dir)
        p.i=100/len(poslist)
        update_process_bar(0)
        update_process_label("Focusing")
        print(get_time()+"start focus image")
        add_highlight_from_scope(get_time()+"start focus image")
        p.core.set_shutter_open(False)
        for index, row in poslist.iterrows():
            update_process_bar(p.i)
            if p.cancel_process ==1:
                txt=get_time()+"process canceled!"
                print(txt)
                p.write_log(txt)
                p.core.set_position("DA Z Stage", p.piezo_middle_pos)
                add_highlight_from_scope(txt)
                break
            pos = row['position']
            if p.piezo==1:
                try:
                    x = row['x']
                    y = row['y']
                    p.core.set_xy_position(x, y)
                    p.core.wait_for_device("XYStage")
                    print("XYStage ready")
                    txt = get_time() + "XYStage ready" + "\n"
                    p.write_log(txt)
                    z = row['z']
                    p.core.set_position("ZDrive", z)
                    p.core.wait_for_device("ZDrive")
                    print("ZDrive ready")
                    txt = get_time() + "ZDrive ready" + "\n"
                    p.write_log(txt)
                    p.core.set_position("DA Z Stage", p.piezo_middle_pos)
                    p.core.wait_for_device("DA Z Stage")
                    print("DA Z Stage")
                    txt = get_time() + "DA Z Stage ready" + "\n"
                    p.write_log(txt)
                    with Acquisition(directory=os.path.join(p.pos_path, "focus" + p.cycle), name=pos, show_display=False) as acq:
                        acq.acquire(p.piezo_event)
                        acq.mark_finished()
                    p.core.stop_stage_sequence('DA Z Stage')
                    p.core.wait_for_device("DA Z Stage")
                except Exception as e:
                    time.sleep(3)
                    p.core.stop_stage_sequence('DA Z Stage')
                    x = row['x']
                    y = row['y']
                    p.core.set_xy_position(x, y)
                    p.core.wait_for_device("XYStage")
                    print("XYStage ready")
                    txt = get_time() + "XYStage ready" + "\n"
                    p.write_log(txt)
                    z = row['z']
                    p.core.set_position("ZDrive", z)
                    p.core.wait_for_device("ZDrive")
                    print("ZDrive ready")
                    txt = get_time() + "ZDrive ready" + "\n"
                    p.write_log(txt)
                    piezo_z = 185
                    p.core.set_position("DA Z Stage", piezo_z)
                    p.core.wait_for_device("DA Z Stage")
                    print("DA Z Stage")
                    txt = get_time() + "DA Z Stage" + "\n"
                    p.write_log(txt)
                    with Acquisition(directory=os.path.join(p.pos_path, "focus" + p.cycle), name=pos,
                                     show_display=False) as acq:
                        acq.acquire(p.piezo_event)
                        acq.mark_finished()
                    p.core.stop_stage_sequence('DA Z Stage')
                    p.core.wait_for_device("DA Z Stage")

            else:
                pass
            p.i=p.i+100/len(poslist)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.find_focus_plane, pos) for pos in poslist["position"].tolist()]
        try:
            done, not_done = wait(futures)
            results = [future.result() for future in done]
        except Exception as e:
            print(f"Error processing position: {e}")
        try:
            copy_dic(p.pos_path, "focus" + p.cycle, "dicfocus" + p.cycle)
            diff = save_offset_and_json(p.pos_path, p.cycle + ".csv", p.z_new_ls, p.cycle + ".pos",p.z_dir)
            for i in range(len(diff)):
                if abs(diff[i]) >= 20:
                    #p.focus_status = 0
                    txt = get_time() + p.cycle + ' extrem focus change detected at ' + str(
                        i) + " position!\n"
                    update_error(txt)
                    p.write_log(txt)
                    p.focus_bad = 1
            if p.focus_bad == 0:
                p.focus_status = 1
                print(p.cycle+" focuse thread! I am finished!Thread closed!")
            p.focus_status = 1
        except Exception as e:
            txt=get_time()+f"focus is wrong or cancelled: {e}"
            update_error(txt)
            diff=0
        return diff
