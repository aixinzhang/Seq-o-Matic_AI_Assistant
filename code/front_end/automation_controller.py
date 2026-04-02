"""Automation controller for the Seq-o-Matic system.

Orchestrates the full experiment automation loop: fluidics sequences,
imagecycle00 focusing, and multi-cycle imaging pipelines.
"""

import os
import time
import json
import shutil
from threading import Thread

import pandas as pd

from front_end.logwindow import (
    add_highlight_mainwindow, update_error,
)
from system.image_acquisition_and_analysis_system import scope, get_pos_data, single_createtiles


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


class AutomationController:
    """Orchestrates the full experiment automation: fluidics, focusing, alignment, tiling, and imaging.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def start_sequence(self):
        """Recursively execute the next step in the protocol list (fluidics, imagecycle00, or imaging) until all rounds complete."""
        if self.app.process_index > self.app.process_index_limite:
            txt = _get_time() + "All rounds finished!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.fluidics.disconnect_pump()
            self.app.fluidics.disconnect_selector()
            self.app.fluidics.disconnect_relay()
            self.app.fluidics.disconnect_heater()
            txt = _get_time() + "Upload data to server!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            if os.path.exists(os.path.join(
                self.app.scope.maxprojection_drive,
                self.app.pos_path[3:] + "_maxprojection",
            )):
                txt = _get_time() + "Upload images to server!\n"
                self.app.write_log(txt)
                add_highlight_mainwindow(txt)
                self.app.scope.send_to_server(self.app.pos_path)
                txt = _get_time() + "Upload images is finished!\n"
                self.app.write_log(txt)
                add_highlight_mainwindow(txt)

            txt = _get_time() + "Upload files to server!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.scope.send_protocol(self.app.pos_path)
            txt = _get_time() + "Upload files is finished!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.all_autobtn_normal()
            self.app.cancel_sequence_btn['state'] = "disable"
            return

        self.app.process_cycle = self.app.process_ls[self.app.process_index]
        txt = _get_time() + "start " + self.app.process_cycle + "\n"
        self.app.write_log(txt)
        add_highlight_mainwindow(txt)
        if "Fluidics_sequence" in self.app.process_cycle:
            self.app.fluidics.pump.driver.setFlowRate(1.5)
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_fluidics()
            try:
                self.app.protocol = self.app.fluidics.find_protocol(self.app.process_cycle)
            except (KeyError, FileNotFoundError, ValueError) as e:
                self.app.fluidics.disconnect_pump()
                self.app.fluidics.disconnect_selector()
                self.app.fluidics.disconnect_relay()
                self.app.fluidics.disconnect_heater()
                self.app.all_autobtn_normal()
                self.app.cancel_sequence_btn['state'] = "disable"
                from tkinter import messagebox
                messagebox.showinfo(title="Protocol issue", message="check protocol file, the format is wrong")
                return
            t = Thread(target=self.app.run_fluidics_cycle, args=(self.app.protocol,))
            t.start()
            # Wait for fluidics to signal imaging can start (or cancel)
            while not self.app.fluidics.start_image_event.wait(timeout=2):
                if self.app.cancel == 1:
                    break
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        elif "imagecycle00" in self.app.process_cycle:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_image()
            self.app.scope.cancel_process = 0
            self.app.current_cycle = "imagecycle00"
            t = Thread(target=self.app.do_focus_thread)
            t.start()
            # Wait for focus to complete (or cancel)
            while self.app.scope.focus_status != 1:
                if self.app.cancel == 1:
                    break
                time.sleep(2)
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        else:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_image()
            self.app.scope.cancel_process = 0
            self.app.current_cycle = self.app.process_cycle[11:]
            self.image_auto()
            # Wait for max projection to complete (or cancel)
            while self.app.scope.max_projection_status != 1:
                if self.app.cancel == 1:
                    break
                time.sleep(2)
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(10)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return

    def image_auto(self):
        """Execute the full automated imaging pipeline: focus, align, tile, then max-project with live view."""
        if self.app.cancel == 1:
            pass
        else:
            self.app.do_focus_thread()
            self.app.align_and_draw_thread()
            self.app.tile_and_draw_thread()
        if self.app.cancel == 1:
            pass
        else:
            t1 = Thread(target=self.app.maxprojection_thread)
            t1.start()
            t2 = Thread(target=self.app.plot_live_view_thread)
            t2.start()

    def check_files(self):
        """Validate that all required input files exist before starting the automation sequence."""
        self.check_imagecycle00()

    def check_imagecycle00(self):
        """Verify that cycle00 position files and reference folders exist when image cycles are in the protocol."""
        if "imagecycle00" in self.app.process_ls:
            if not os.path.exists(os.path.join(self.app.pos_path, "cycle00.pos")):
                from tkinter import messagebox
                messagebox.showinfo(title="Config failure ",
                                    message="Please create cycle00 coordinates first!")
                update_error("Please create cycle00 coordinates first!")
                return
            else:
                self.app.check_file = self.app.scope.check_cycle00()
        else:
            check = [1 for i in self.app.process_ls if "imagecycle" in i]
            if sum(check) == 0:
                self.app.check_file = 1
                return
            else:
                if not os.path.exists(os.path.join(self.app.pos_path, "dicfocuscycle00")):
                    update_error("Missing dicfocuscycle00")
                    return
                if not os.path.exists(os.path.join(self.app.pos_path, "pre_adjusted_pos.pos")):
                    update_error("Missing pre_adjusted_pos.pos")
                    return
                else:
                    self.app.check_file = 1

    def check_storage(self):
        """Check whether the max-projection disk has enough free space for the expected number of imaging rounds."""
        n_image_round = sum([1 for i in self.app.process_ls if "image" in i])
        if n_image_round != 0:
            if os.path.exists(os.path.join(self.app.pos_path, "cycle00.pos")):
                with open(os.path.join(self.app.pos_path, "cycle00.pos")) as f:
                    d = json.load(f)
            else:
                with open(os.path.join(self.app.pos_path, "pre_adjust_pos.pos")) as f:
                    d = json.load(f)
            focus_poslist = pd.DataFrame(
                [get_pos_data(item, 1) for item in d['map']['StagePositions']['array']],
            )[['position', 'x', 'y', 'z', 'piezo']]
            full_df = single_createtiles(
                focus_poslist, self.app.scope.imwidth,
                self.app.scope.overlap, self.app.scope.pixelsize,
            )
            tile = len(full_df)
            tile_size = 102400920
            totalsize = tile * tile_size * n_image_round
            otal, used, free = shutil.disk_usage(os.path.join(self.app.scope.maxprojection_drive))
            if free > totalsize:
                storage_check = 1
                txt = _get_time() + "Maxprojection disk is available!\n"
                self.app.write_log(txt)
                add_highlight_mainwindow(txt)
            else:
                storage_check = 0
                txt = _get_time() + "Maxprojection disk doesn't have enough space!\n"
                self.app.write_log(txt)
                add_highlight_mainwindow(txt)
        else:
            storage_check = 1

        return storage_check

    def all_autobtn_disable(self):
        """Disable all primary action buttons to prevent user interaction during a running process."""
        self.app.browse_btn_auto['state'] = "disable"
        self.app.browse_btn_manual['state'] = "disable"
        self.app.exp_btn_manual['state'] = "disable"
        self.app.exp_btn_auto['state'] = "disable"
        self.app.recipe_btn['state'] = "disable"
        self.app.info_btn_auto['state'] = "disable"
        self.app.device_btn['state'] = "disable"
        self.app.brain_btn['state'] = "disable"
        self.app.prime_btn['state'] = "disable"
        self.app.start_sequence_btn['state'] = "disable"
        self.app.fill_single_btn['state'] = "disable"

    def all_autobtn_normal(self):
        """Re-enable all primary action buttons after a process completes or is cancelled."""
        self.app.browse_btn_auto['state'] = "normal"
        self.app.browse_btn_manual['state'] = "normal"
        self.app.exp_btn_manual['state'] = "normal"
        self.app.exp_btn_auto['state'] = "normal"
        self.app.recipe_btn['state'] = "normal"
        self.app.info_btn_auto['state'] = "normal"
        self.app.device_btn['state'] = "normal"
        self.app.brain_btn['state'] = "normal"
        self.app.prime_btn['state'] = "normal"
        self.app.start_sequence_btn['state'] = "normal"
        self.app.fill_single_btn['state'] = "normal"
        self.app.cancel_sequence_btn['state'] = "normal"

    def write_log(self, txt):
        """Append the given text to the log.txt file in the work directory."""
        try:
            f = open(os.path.join(self.app.pos_path, "log.txt"), "a")
            f.write(txt)
            f.close()
        except OSError as e:
            print(f"Error writing log: {e}")
