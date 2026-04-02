"""Experiment configuration panel for the Seq-o-Matic GUI.

Handles slice-per-slide formatting, pixel size changes, server/AWS configuration,
cycle detail assignment, sequence checking, recipe building, and heater assignment.
"""

import os
import json
import tkinter as tk
from tkinter import (
    ttk, StringVar, IntVar, NORMAL, DISABLED, Button, Checkbutton,
    messagebox,
)

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image

from front_end.logwindow import (
    add_highlight_mainwindow, update_error, widge_attr,
)
from front_end.recipe_builder import process_builder


class ExperimentConfigPanel:
    """Manages experiment configuration options such as slices, pixel size, server, AWS, recipes, and heaters.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def slice_per_slide_reformat(self):
        """Parse the comma-separated slice-per-slide input from the auto tab into a list of integers."""
        try:
            a = self.app.slice_number_field_auto.get()
            num = [int(x) for x in a.split(',')]
            self.app.slice_per_slide = num
        except ValueError as e:
            self.app.log_update = 0
            messagebox.showinfo(title="Wrong Input", message="Slice per slide is wrong!")
            self.app.slice_per_slide = None

    def slice_per_slide_reformat_manual(self):
        """Parse the comma-separated slice-per-slide input from the manual tab into a list of integers."""
        try:
            a = self.app.slice_number_field_manual.get()
            num = [int(x) for x in a.split(',')]
            self.app.slice_per_slide = num
        except ValueError as e:
            self.app.log_update = 0
            messagebox.showinfo(title="Wrong Input", message="Slice per slide is wrong!")
            self.app.slice_per_slide = None

    def change_pixel_handler_auto(self):
        """Toggle the pixel size entry field between editable and disabled on the auto tab."""
        if self.app.change_pixel_value.get() == 1:
            self.app.pixel_size_field_auto.config(state=NORMAL)
        else:
            t = self.app.pixel_size_field_auto.get()
            self.app.pixel_size.set(t)
            self.app.pixel_size_field_auto.config(state=DISABLED)

    def change_pixel_handler_manual(self):
        """Toggle the pixel size entry field between editable and disabled on the manual tab."""
        if self.app.change_pixel_value.get() == 1:
            self.app.pixel_size_field_manual.config(state=NORMAL)
        else:
            t = self.app.pixel_size_field_manual.get()
            self.app.pixel_size.set(t)
            self.app.pixel_size_field_manual.config(state=DISABLED)

    def change_server_auto(self):
        """Toggle the storage server fields between editable and disabled on the auto tab."""
        if self.app.change_server_value.get() == 1:
            self.app.server_account_lb_auto.config(fg=widge_attr.normal_color)
            self.app.server_lb_auto.config(fg=widge_attr.normal_color)
            self.app.server_field_auto["state"] = "normal"
            self.app.account_field_auto["state"] = "normal"
        else:
            self.app.server_account_lb_auto.config(fg=widge_attr.disable_color)
            self.app.server_lb_auto.config(fg=widge_attr.disable_color)
            self.app.server_field_auto["state"] = "disable"
            self.app.account_field_auto["state"] = "disable"

    def change_server_manual(self):
        """Toggle the storage server fields between editable and disabled on the manual tab."""
        if self.app.change_server_value.get() == 1:
            self.app.server_account_lb_manual.config(fg=widge_attr.normal_color)
            self.app.server_lb_manual.config(fg=widge_attr.normal_color)
            self.app.server_field_manual["state"] = "normal"
            self.app.account_field_manual["state"] = "normal"
        else:
            self.app.server_account_lb_manual.config(fg=widge_attr.disable_color)
            self.app.server_lb_manual.config(fg=widge_attr.disable_color)
            self.app.server_field_manual["state"] = "disable"
            self.app.account_field_manual["state"] = "disable"

    def upload_to_aws_auto(self):
        """Toggle the AWS credential fields between editable and disabled on the auto tab."""
        if self.app.upload_aws_value.get() == 1:
            self.app.aws_account_lb_auto.config(fg=widge_attr.normal_color)
            self.app.aws_password_lb_auto.config(fg=widge_attr.normal_color)
            self.app.aws_account_field_auto["state"] = "normal"
            self.app.aws_pwd_field_auto["state"] = "normal"
        else:
            self.app.aws_account_lb_auto.config(fg=widge_attr.disable_color)
            self.app.aws_password_lb_auto.config(fg=widge_attr.disable_color)
            self.app.aws_account_field_auto["state"] = "disable"
            self.app.aws_pwd_field_auto["state"] = "disable"

    def upload_to_aws_manual(self):
        """Toggle the AWS credential fields between editable and disabled on the manual tab."""
        if self.app.upload_aws_value.get() == 1:
            self.app.aws_account_lb_manual.config(fg=widge_attr.normal_color)
            self.app.aws_password_lb_manual.config(fg=widge_attr.normal_color)
            self.app.aws_account_field_manual["state"] = "normal"
            self.app.aws_pwd_field_manual["state"] = "normal"
        else:
            self.app.aws_account_lb_manual.config(fg=widge_attr.disable_color)
            self.app.aws_password_lb_manual.config(fg=widge_attr.disable_color)
            self.app.aws_account_field_manual["state"] = "disable"
            self.app.aws_pwd_field_manual["state"] = "disable"

    def assign_cycle_detail(self):
        """Read the protocol.csv file and build the ordered process list, inserting imagecycle00 if needed."""
        if not os.path.exists(os.path.join(self.app.pos_path, "protocol.csv")):
            from front_end.Widgets import get_time
            txt = get_time() + "couldn't find protocol.csv file, please create protocol if choose using user defined protocol!"
            update_error(txt)
            return
        df = pd.read_csv(os.path.join(self.app.pos_path, "protocol.csv"))
        self.app.process_ls = df['process'].tolist()
        check = [1 for i in self.app.process_ls if "imagecycle" in i]
        if sum(check) >= 1:
            if "imagecycle00" not in self.app.process_ls:
                if not os.path.exists(os.path.join(self.app.pos_path, "dicfocuscycle00")):
                    for i in range(len(self.app.process_ls)):
                        cycle = self.app.process_ls[i]
                        if "imagecycle" in cycle:
                            self.app.process_ls.insert(i, 'imagecycle00')
                            break
        add_highlight_mainwindow("protocol has beed assigned!" + "\n")
        self.app.write_log("protocol has beed assigned!")

    def check_sequence(self, n_chamber):
        """Validate all fluidics sequences in the protocol, compute total reagent volumes, and save reagents.csv."""
        add_highlight_mainwindow("Start checking the sequences.....\n")
        fluidics_sequence = [i for i in self.app.process_ls if "Fluidics" in i]
        df = pd.DataFrame(
            list(self.app.fluidics.selector_fluidics_dict.items()),
            columns=['address', 'Reagent_Name'],
        )
        df['Amount_ml'] = 0
        df['status'] = "unuse"
        for sequence in fluidics_sequence:
            Sequence = self.app.fluidics.find_protocol(sequence)
            for i in range(len(Sequence)):
                step = Sequence[i]
                if step['device'] == "pump":
                    df.loc[df['address'] == int(step['source']), 'Amount_ml'] += step['volume']
                    df.loc[df['address'] == int(step['source']), 'status'] = "use"
                else:
                    pass
        df['Amount_ml'] = df['Amount_ml'] * n_chamber + 1
        df['prepared'] = 0
        df['left'] = 0
        df['note'] = ""
        df.to_csv(os.path.join(self.app.pos_path, 'reagents.csv'), index=False)
        add_highlight_mainwindow("reagent amount saved to reagents.csv \n")
        add_highlight_mainwindow("Finish checking the sequences.....\n")

    def recipe_btn_handler(self):
        """Launch the protocol/recipe builder window for the current work directory."""
        self.app.pb = process_builder()
        self.app.pb.create_window(self.app.work_path_field_auto.get())

    def assign_heater(self):
        """Open a popup window to assign heat stages to individual slide chambers."""
        self.app.heater_popup = tk.Tk()
        self.app.heater_popup.geometry("410x350")
        self.app.heater_popup.title("Assign heater")

        self.app.slide1_checked_value = IntVar()
        self.app.slide1_cbox = Checkbutton(
            self.app.heater_popup, text="Slide 1 included",
            command=self.assign_chamber1_heater,
            fg=widge_attr.normal_color,
            variable=self.app.slide1_checked_value, onvalue=1, offvalue=0,
        )
        self.app.slide1_cbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.app.slide2_checked = IntVar()
        self.app.slide2_checked.set(0)
        self.app.slide2_cbox = Checkbutton(
            self.app.heater_popup, text="Slide 2 included",
            command=self.assign_chamber2_heater,
            fg=widge_attr.normal_color,
            variable=self.app.slide2_checked, onvalue=1, offvalue=0,
        )
        self.app.slide2_cbox.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.app.slide3_checked = IntVar()
        self.app.slide3_checked.set(0)
        self.app.slide3_cbox = Checkbutton(
            self.app.heater_popup, text="Slide3  included",
            command=self.assign_chamber3_heater,
            fg=widge_attr.normal_color,
            variable=self.app.slide3_checked, onvalue=1, offvalue=0,
        )
        self.app.slide3_cbox.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

        figure = plt.Figure(figsize=(1, 2), dpi=100)
        slide_img1 = FigureCanvasTkAgg(figure, master=self.app.heater_popup)
        slide_img1.get_tk_widget().grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        slide_img2 = FigureCanvasTkAgg(figure, master=self.app.heater_popup)
        slide_img2.get_tk_widget().grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        slide_img3 = FigureCanvasTkAgg(figure, master=self.app.heater_popup)
        slide_img3.get_tk_widget().grid(row=1, column=2, padx=10, pady=10, sticky="nsew")
        slideimg = Image.open(os.path.join(self.app.cwd, "front_end", "slide.png"))
        plotslide1 = figure.add_subplot(111)
        plotslide1.imshow(slideimg)
        plotslide1.get_xaxis().set_visible(False)
        plotslide1.get_yaxis().set_visible(False)
        slide_img1.draw()
        slide_img2.draw()
        slide_img3.draw()

        with open(os.path.join(self.app.system_path, "config_file", "Heat_stage.json"), 'r') as r:
            heater_list_cfg = json.load(r)
        heater_list = [i['heat_stage'] for i in heater_list_cfg]
        heater_list = heater_list + [""]

        self.app.heater1 = StringVar()
        self.app.slide_heater1 = ttk.Combobox(self.app.heater_popup, textvariable=self.app.heater1, width=10)
        self.app.slide_heater1['value'] = heater_list
        self.app.slide_heater1['state'] = "readonly"
        self.app.slide_heater1.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.app.slide_heater1.config(state=DISABLED)

        self.app.heater2 = StringVar()
        self.app.slide_heater2 = ttk.Combobox(self.app.heater_popup, textvariable=self.app.heater2, width=10)
        self.app.slide_heater2['value'] = heater_list
        self.app.slide_heater2['state'] = "readonly"
        self.app.slide_heater2.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")
        self.app.slide_heater2.config(state=DISABLED)

        self.app.heater3 = StringVar()
        self.app.slide_heater3 = ttk.Combobox(self.app.heater_popup, textvariable=self.app.heater3, width=10)
        self.app.slide_heater3['value'] = heater_list
        self.app.slide_heater3['state'] = "readonly"
        self.app.slide_heater3.grid(row=2, column=2, padx=10, pady=10, sticky="nsew")
        self.app.slide_heater3.config(state=DISABLED)

        self.app.assign_heater_btn = Button(
            self.app.heater_popup, text="Confirm",
            command=self.assign_heater_to_slide,
            bd=widge_attr.normal_edge, fg="#1473cc",
        )
        self.app.assign_heater_btn.grid(row=3, column=1, padx=10, pady=10, sticky="nsew")

    def assign_chamber1_heater(self):
        """Enable the heater dropdown for slide chamber 1."""
        self.app.slide_heater1.config(state=NORMAL)

    def assign_chamber2_heater(self):
        """Enable the heater dropdown for slide chamber 2."""
        self.app.slide_heater2.config(state=NORMAL)

    def assign_chamber3_heater(self):
        """Enable the heater dropdown for slide chamber 3."""
        self.app.slide_heater3.config(state=NORMAL)

    def assign_heater_to_slide(self):
        """Confirm the heater-to-slide assignment, store the mapping, and close the popup."""
        self.app.assigned_heater = 1
        self.app.heater_dict = {
            "chamber1": self.app.slide_heater1.get(),
            "chamber2": self.app.slide_heater2.get(),
            "chamber3": self.app.slide_heater3.get(),
        }
        self.app.heater_dict = {k: v for k, v in self.app.heater_dict.items() if v != ''}
        self.app.chamber_number = len(self.app.heater_dict)
        self.app.chamber_list = list(self.app.heater_dict.keys())
        self.app.heater_popup.destroy()
