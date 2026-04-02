"""Workspace and directory selection panel for the Seq-o-Matic GUI.

Handles browsing for work directories and opening experiment profile editors
in both auto and manual modes.
"""

import os
from tkinter import filedialog, messagebox

from front_end.experiment_profile import Exp_profile


class WorkspacePanel:
    """Manages workspace directory selection and experiment profile creation.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def browse_handler_auto(self):
        """Open a directory chooser dialog and set the selected path in the auto tab work path field."""
        self.app.tempdir = self.search_for_file_path()
        self.app.path.set(self.app.tempdir)
        self.app.work_path_field_auto.config(textvariable=self.app.path)

    def browse_handler_manual(self):
        """Open a directory chooser dialog and set the selected path in the manual tab work path field."""
        self.app.tempdir = self.search_for_file_path()
        self.app.path.set(self.app.tempdir)
        self.app.work_path_field_manual.config(textvariable=self.app.path)

    def search_for_file_path(self):
        """Display a tkinter directory selection dialog and return the chosen path."""
        self.app.currdir = os.getcwd()
        self.app.tempdir = filedialog.askdirectory(
            parent=self.app.parent_window,
            initialdir=self.app.currdir,
            title='Please select a directory',
        )
        if len(self.app.tempdir) > 0:
            print("You chose: %s" % self.app.tempdir)
        return self.app.tempdir

    def exp_btn_handler(self):
        """Open the experiment profile editor for the auto tab's work directory."""
        if self.app.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        else:
            work_path = self.app.work_path_field_auto.get()
            Exp_profile(work_path)

    def exp_btn_handler_manual(self):
        """Open the experiment profile editor for the manual tab's work directory."""
        if self.app.work_path_field_manual.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        else:
            work_path = self.app.work_path_field_manual.get()
            Exp_profile(work_path)

    def create_exp_auto(self):
        """Validate auto tab inputs, initialize the microscope and fluidics systems, and prepare the full automation protocol."""
        import json
        import pandas as pd
        from front_end.logwindow import (
            Log_window, clear_error, clear_log,
            add_highlight_mainwindow, update_error,
        )
        from system.fluidics_exchange_system import FluidicSystem
        from system.image_acquisition_and_analysis_system import scope

        clear_error()
        clear_log()
        self.app.clear_align_canvas()
        self.app.clear_tile_canvas()
        self.app.clear_focus_canvas()
        self.app.slice_per_slide_reformat()
        self.app.cancel = 0
        self.app.skip_alignment = self.app.mock_alignment.get()
        Log_window.warning_stw.delete('1.0', 'end')
        if self.app.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
            return
        self.app.pos_path = self.app.work_path_field_auto.get()
        if not os.path.exists(os.path.join(self.app.pos_path, "temp.txt")):
            open(os.path.join(self.app.pos_path, "temp.txt"), 'w')
        if not os.path.exists(os.path.join(self.app.pos_path, "log.txt")):
            open(os.path.join(self.app.pos_path, "log.txt"), 'w')
        # Attach Python logging file handler to the experiment log
        from logging_config import update_log_file
        update_log_file(os.path.join(self.app.pos_path, "log.txt"))
        self.app.server = self.app.account_field_auto.get() + "@" + self.app.server_field_auto.get()
        self.app.assign_cycle_detail()
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.app.scope_cfg = json.load(r)
            self.app.imwidth = self.app.scope_cfg[0]["imwidth"]
        try:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
        except Exception as e:
            messagebox.showinfo(title="Config failure ",
                                message="Please run micromanager first!")
            update_error("Please run micromanager first!")
            return
        if self.app.assigned_heater == 0:
            self.app.heater_dict = {
                'chamber1': "heatstage1",
                'chamber2': "heatstage2",
                'chamber3': "heatstage3",
            }
            self.app.chamber_number = 3
        self.app.fluidics = FluidicSystem(
            system_path=self.app.system_path,
            pos_path=self.app.pos_path,
            slide_hearter_dictionary=self.app.heater_dict,
        )
        self.app.check_sequence(self.app.chamber_number)

    def create_exp_manual(self):
        """Validate manual tab inputs, initialize the microscope scope, and prepare for manual imaging of a single cycle."""
        import json
        import pandas as pd
        from front_end.logwindow import (
            clear_error, clear_log, add_highlight_mainwindow, update_error,
        )
        from system.image_acquisition_and_analysis_system import scope

        clear_error()
        clear_log()
        self.app.clear_align_canvas()
        self.app.clear_tile_canvas()
        self.app.clear_focus_canvas()
        self.app.cycle_number = self.app.sb1_cycle_number.get()
        self.app.current_cycle = self.app.current_c.get() + self.app.sb1_cycle_number.get().zfill(2)
        if "00" in self.app.current_cycle:
            self.app.current_cycle = "cycle00"

        self.app.skip_alignment = self.app.mock_alignment.get()
        self.app.protocol_list_index = 0
        self.app.server = self.app.account_field_manual.get() + "@" + self.app.server_field_manual.get()
        if self.app.work_path_field_manual.get() == "":
            messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
            return
        self.app.pos_path = self.app.work_path_field_manual.get()
        if self.app.current_c.get() == "":
            messagebox.showinfo(title="Wrong Input", message="current cycle type can't be empty")
            return
        if self.app.slice_number_field_manual.get() == "":
            messagebox.showinfo(title="Wrong Input", message="slice per slide can't be empty")
            return
        self.app.slice_per_slide_reformat_manual()
        self.app.protocol_list = [self.app.current_cycle]
        if "00" in self.app.current_cycle:
            self.app.align_btn["state"] = "disable"
            self.app.tile_btn["state"] = "disable"
            self.app.max_btn["state"] = "disable"
        else:
            self.app.align_btn["state"] = "normal"
            self.app.tile_btn["state"] = "normal"
            self.app.max_btn["state"] = "normal"
        if not os.path.exists(os.path.join(self.app.pos_path, "log.txt")):
            open(os.path.join(self.app.pos_path, "log.txt"), 'a').close()
        # Attach Python logging file handler to the experiment log
        from logging_config import update_log_file
        update_log_file(os.path.join(self.app.pos_path, "log.txt"))
        print(self.app.slice_per_slide)
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.app.scope_cfg = json.load(r)
            self.app.imwidth = self.app.scope_cfg[0]["imwidth"]
        try:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
        except Exception as e:
            messagebox.showinfo(title="Config failure ",
                                message="Please run micromanager first!")
            update_error("Please run micromanager first!")
            return
        from front_end.Widgets import get_time
        txt = (get_time() + "\n" + "work directory: " + self.app.pos_path + "\n"
               + "Current cycle: " + self.app.protocol_list[self.app.protocol_list_index] + "\n")
        print(txt)
        self.app.write_log(txt)
        add_highlight_mainwindow(txt)
        if not os.path.exists(os.path.join(self.app.pos_path, "manual_process_record.csv")):
            df = pd.DataFrame(columns=["protocol"])
            df["protocol"] = "imagecycle_" + self.app.current_cycle
            df.to_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"), index=False)
        else:
            df = pd.read_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"))
            df.loc[len(df.index)] = ["imagecycle_" + self.app.current_cycle]
            df.to_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"), index=False)
        self.app.focus_btn["state"] = "normal"
        self.app.scope.move_to_image()
