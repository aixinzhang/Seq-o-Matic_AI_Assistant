"""GUI widget module for the Seq-o-matics automated sequencing system.

Provides the main window_widgets class that builds the tkinter-based user interface
for controlling fluidics, imaging, and automated sequencing experiments in both
auto and manual modes.  Method implementations are delegated to focused panel
modules under front_end.panels and front_end.automation_controller.
"""

import os.path
import tkinter as tk
from tkinter import ttk, StringVar, scrolledtext, Button, END, DISABLED, NORMAL, Label, Entry, Checkbutton, IntVar, Spinbox, PhotoImage
from datetime import datetime

from pytz import timezone
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import cv2

from front_end.logwindow import (
    Log_window, widge_attr, hattop_convert, denoise,
    update_error, clear_error, clear_log,
    add_highlight_from_scope, add_device_information,
    add_fluidics_status, add_fluidics_reagent, add_highlight_mainwindow,
    update_process_bar, update_process_label,
    draw_liveview, clear_liveview_canvas,
)

from front_end.panels.workspace_panel import WorkspacePanel
from front_end.panels.experiment_config_panel import ExperimentConfigPanel
from front_end.panels.device_panel import DevicePanel
from front_end.panels.fluidics_control_panel import FluidicsControlPanel
from front_end.panels.imaging_control_panel import ImagingControlPanel
from front_end.panels.status_panel import StatusPanel
from front_end.automation_controller import AutomationController


def clear_canvas(canvas):
    """Remove all drawn items from a matplotlib FigureCanvasTkAgg widget."""
    for item in canvas.get_tk_widget().find_all():
       canvas.get_tk_widget().delete(item)
def get_time():
    """Return the current US/Pacific timestamp as a formatted string with a trailing newline."""
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time
def get_date():
    """Return the current US/Pacific date as a YYYY-MM-DD string."""
    time_now = timezone('US/Pacific')
    date = str(datetime.now(time_now))[0:10]
    return date
def create_folder_file(pos_path,name):
    """Create a subdirectory under pos_path if it does not already exist."""
    if not os.path.exists(os.path.join(pos_path,name)):
        os.makedirs(os.path.join(pos_path,name))

filterSize =(10, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT,  filterSize)
color_array=np.array([[0,4,4],[1.5,1.5,0],[1,0,1],[0,0,1.5]])

def hattop_convert(x):
    """Apply a morphological top-hat transform to an image array for background subtraction."""
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)
def denoise(x):
    """Zero out pixel values below the 85th percentile to remove low-intensity noise."""
    x[x<np.percentile(x, 85)]=0
    return x
class widge_attr:
    """Shared visual style constants (colors, border widths) used across GUI widgets."""
    normal_edge=3
    disable_edge = 0.9
    normal_color = '#0f0201'
    disable_color = '#bab8b8'
    warning_color='#871010'
    black_color='#0a0000'
    yellow_color="#e0c80b"


class window_widgets:
    """Main GUI controller that builds all tkinter widgets and orchestrates fluidics, imaging, and automation workflows.

    Provides both an 'Auto System' tab for fully automated sequencing runs and a 'Manual System'
    tab for step-by-step operator-driven imaging and fluidics operations.

    Method implementations are delegated to focused panel classes:
    - WorkspacePanel: directory browsing, experiment profile
    - ExperimentConfigPanel: slices, pixel size, server, AWS, recipes, heaters
    - DevicePanel: hardware device configuration
    - FluidicsControlPanel: priming, pumping, washing, automation start
    - ImagingControlPanel: focus, align, tile, max-projection, live view
    - StatusPanel: canvas clearing, notes, AWS upload
    - AutomationController: full experiment automation loop
    """
    def __init__(self,mainwindow,path):
        """Initialize all GUI frames, labels, buttons, fields, and canvases for auto and manual tabs.

        Args:
            mainwindow: The root tkinter window that hosts all widgets.
            path: The system-level path used to locate logos, config files, and resources.
        """
        # -- Create panel delegates (before widget creation so commands can reference them) --
        self._workspace = WorkspacePanel(self)
        self._config = ExperimentConfigPanel(self)
        self._device = DevicePanel(self)
        self._fluidics_ctl = FluidicsControlPanel(self)
        self._imaging = ImagingControlPanel(self)
        self._status = StatusPanel(self)
        self._automation = AutomationController(self)

        self.device_status = {
            "pump_group": 0,
            "selector_group": 0,
            "relay_group": 0,
            "heater_group": 0}
        self.wash_inchamber=0
        self.cwd = os.getcwd()

        with open(os.path.join(self.cwd,"device","pump_speed_calibration.txt"), 'r') as f:
            self.pump_pre_speed = f.readlines()[-1]
        f.close()
        print(self.pump_pre_speed)
        self.assigned_heater = 0
        self.system_path=path
        self.main=mainwindow
        self.parent_window = mainwindow
        self.auto_image = PhotoImage(file=os.path.join( self.system_path,"logo", "auto_logo.png"))
        self.manual_image = PhotoImage(file=os.path.join(self.system_path,"logo", "hand.png"))
        self.frame0 = tk.Frame(self.main, bg=self.main.cget('bg'))
        self.frame0.grid(row=0, column=0, sticky="nsew")
        self.notebook = ttk.Notebook(self.frame0)
        self.notebook.grid(row=0, column=0)


        self.auto_tab = ttk.Frame(self.notebook)
        self.manual_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.auto_tab, text='Auto System', image=self.auto_image, compound=tk.LEFT)
        self.notebook.add(self.manual_tab, text='Manual System', image=self.manual_image, compound=tk.LEFT)

        ## section
        self.section1_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 1 Choose work directory",width=600)
        self.section1_lbf_auto.pack_propagate(False)
        self.section1_lbf_auto.grid(row=0, column=0, padx=3, pady=3,sticky="n")



        self.section2_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 2 Fill process details",width=600)
        self.section2_lbf_auto.pack_propagate(False)
        self.section2_lbf_auto.grid(row=1, column=0, padx=3, pady=3,sticky="n")


        self.section3_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 3 Automation functions", width=600)
        self.section3_lbf_auto.pack_propagate(False)
        self.section3_lbf_auto.grid(row=3, column=0, padx=3, pady=3, sticky="n")

        self.section3_lbf_manual= tk.LabelFrame(self.manual_tab, text="Section 3 Manual functions", width=600)
        self.section3_lbf_manual.pack_propagate(False)
        self.section3_lbf_manual.grid(row=3, column=0, padx=3, pady=3, sticky="n")




        self.section4_addtion_note = tk.LabelFrame(self.frame0, text="Section 4 Addition notes", width=600)
        self.section4_addtion_note.pack_propagate(False)
        self.section4_addtion_note.grid(row=5, column=0, padx=3, pady=3, sticky="n")

        self.section1_lbf_manual = tk.LabelFrame(self.manual_tab, text="Section 1 Choose work directory", width=600)
        self.section1_lbf_manual.grid(row=0, column=0, padx=3, pady=3, sticky="n")
        #
        self.section2_lbf_manual = tk.LabelFrame(self.manual_tab, text="Section 2 Fill process details", width=600)

        self.section2_lbf_manual.grid(row=1, column=0, padx=3, pady=3, sticky="n")

        ##Frame

        self.frame1 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'),width=500)
        self.frame1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.frame1_1 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'),width=500)
        self.frame1_1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.frame2 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame2.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame2_2 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'), width=500)
        self.frame2_2.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)


        self.frame3 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame3.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.frame3_3 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'), width=500)
        self.frame3_3.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self.frame5 = tk.Frame(self.section3_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame5.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.frame6 = tk.Frame(self.section3_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame6.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame7 = tk.Frame(self.frame0, bg=self.main.cget('bg'), width=500)
        self.frame7.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)

        ##label group
        self.work_path_lb_auto = Label(self.section1_lbf_auto, text="Select your work directory:", bd=1, relief="flat", width=20,
                                  fg=widge_attr.black_color, font=("Arial", 10))
        self.work_path_lb_manual = Label(self.section1_lbf_manual, text="Select your work directory:", bd=1, relief="flat",
                                       width=20,fg=widge_attr.black_color, font=("Arial", 10))

        self.slice_per_slide_lb_auto = Label(self.frame1, text="Slice per slide:", bd=1, relief="flat", width=15,
                                        fg=widge_attr.black_color, font=("Arial", 10))

        self.slice_per_slide_lb_manual = Label(self.frame1_1, text="Slice per slide:", bd=1, relief="flat", width=15,
                                             fg=widge_attr.black_color, font=("Arial", 10))

        self.OR_lb = Label(self.frame1, text="OR", bd=1, relief="flat", width=3,
                           fg=widge_attr.black_color, font=("Arial", 10))

        self.server_account_lb_auto = Label(self.frame2, text="server account:", bd=1, relief="flat", width=10,
                                       fg=widge_attr.disable_color, font=("Arial", 10))

        self.server_lb_auto = Label(self.frame2, text="server name:", bd=1, relief="flat", width=10,
                               fg=widge_attr.disable_color, font=("Arial", 10))

        self.server_account_lb_manual = Label(self.frame2_2, text="server account:", bd=1, relief="flat", width=10,
                                            fg=widge_attr.disable_color, font=("Arial", 10))

        self.server_lb_manual = Label(self.frame2_2, text="server name:", bd=1, relief="flat", width=10,
                                    fg=widge_attr.disable_color, font=("Arial", 10))




        self.aws_account_lb_auto = Label(self.frame3, text="AWS account:", bd=1, relief="flat", width=12,
                                    fg=widge_attr.disable_color, font=("Arial", 10))
        self.aws_password_lb_auto = Label(self.frame3, text="AWS password:", bd=1, relief="flat", width=15,
                                     fg=widge_attr.disable_color, font=("Arial", 10))

        self.aws_account_lb_manual = Label(self.frame3_3, text="AWS account:", bd=1, relief="flat", width=12,
                                         fg=widge_attr.disable_color, font=("Arial", 10))
        self.aws_password_lb_manual = Label(self.frame3_3, text="AWS password:", bd=1, relief="flat", width=15,
                                          fg=widge_attr.disable_color, font=("Arial", 10))




        self.fill_lb=Label(self.frame5, text="Reagent:", bd=1, relief="flat", width=6,
                                     fg=widge_attr.black_color, font=("Arial", 10))

        self.focus_lb = Label(self.frame7, text="Focus shift", bd=1, relief="flat", width=15,
                             fg=widge_attr.black_color, font=("Arial", 10))
        self.align_lb = Label(self.frame7, text="XY-plane shift", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))
        self.tile_lb = Label(self.frame7, text="Tiles", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))
        self.note_lb = Label(self.section4_addtion_note, text="Notes", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))

        self.current_cycle_lb=Label(self.frame1_1, text="Current Cycle:", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))

        self.pump_speed_label = Label(self.frame6, text="Calibrate current pump speed:", bd=1, relief="flat", width=23,
                              fg=widge_attr.black_color, font=("Arial", 10))
        self.pump_speed_unit_label = Label(self.frame6, text="ml/min", bd=1, relief="flat", width=5,
                                      fg=widge_attr.black_color, font=("Arial", 10))
        #button group
        self.browse_btn_auto = Button(self.section1_lbf_auto, text="Browse", command=self.browse_handler_auto,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.exp_btn_auto = Button(self.section1_lbf_auto, text="Fill experiment detail", command=self.exp_btn_handler, width=18,
                              bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.browse_btn_manual = Button(self.section1_lbf_manual, text="Browse", command=self.browse_handler_manual,
                                      bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.exp_btn_manual = Button(self.section1_lbf_manual, text="Fill experiment detail", command=self.exp_btn_handler,
                                   width=18,bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.recipe_btn = Button(self.frame1, text="Create Protocol", command=self.recipe_btn_handler,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.assign_heater_btn = Button(self.frame1, text="Assign Heaters", command=self.assign_heater,
                                        bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.info_btn_auto = Button(self.auto_tab, text="Create Your Experiment",command=self.create_exp_auto,
                               bd=widge_attr.normal_edge, fg="#1473cc")

        self.info_btn_manual = Button(self.manual_tab, text="Create Your Experiment", command=self.create_exp_manual,
                                    bd=widge_attr.normal_edge, fg="#1473cc")

        self.device_btn = Button(self.frame5, text="Devices configuration", command=self.config_device,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.brain_btn = Button(self.frame5, text="Tissue Scanner (optional)", command=self.scan_tissue,
                                bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.prime_btn = Button(self.frame5, text="Prime lines", command=self.prime_btn_check,
                                bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.fill_single_btn = Button(self.frame5, text="Fill", command=self.pump_btn_check,
                                      bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.start_sequence_btn = Button(self.frame6, text="Start Automation process",command=self.start_btn_check,
                                         bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.cancel_sequence_btn = Button(self.frame6, text="Cancel Automation process", command=self.cancel_btn_handler,
                                          bd=widge_attr.normal_edge, fg=widge_attr.warning_color)
        self.cancel_sequence_btn['state'] = "disable"
        self.wash_btn = Button(self.frame6, text="wash tubes", command=self.wash_btn_check,
                               bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.note_btn = Button(self.section4_addtion_note, text="Send note to server", command=self.save_to_note,
                               bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.focus_btn = Button(self.section3_lbf_manual, text="Step 1 Auto Focusing", command=self.focus_btn_handler,
                                bd=widge_attr.normal_edge, fg="#1473cc")
        self.focus_btn["state"] = "disable"

        self.align_btn = Button(self.section3_lbf_manual, text="Step 2 Align with Cycle00", command=self.align_btn_handler,
                                bd=widge_attr.normal_edge, fg="#1473cc")
        self.align_btn["state"] = "disable"
        self.tile_btn = Button(self.section3_lbf_manual, text="Step 3 Creat Tiles", command=self.tile_btn_handler,
                               bd=widge_attr.normal_edge, fg="#1473cc")
        self.tile_btn["state"] = "disable"
        self.max_btn = Button(self.section3_lbf_manual, text="Step 4 Image and Maxprojection", command=self.max_btn_handler,
                              bd=widge_attr.normal_edge, fg="#1473cc")
        self.max_btn["state"] = "disable"

        self.cancle_image_btn = Button(self.section3_lbf_manual, text="Cancel image process", command=self.cancel_manual_process,
                                       bd=widge_attr.normal_edge, fg=widge_attr.warning_color)
        self.cancle_image_btn["state"] = "disable"

        ## Field
        self.path = tk.StringVar()
        self.work_path_field_auto = Entry(self.section1_lbf_auto, relief="groove", width=43)
        self.work_path_field_manual = Entry(self.section1_lbf_manual, relief="groove", width=35)



        self.pump_speed_str = tk.StringVar()
        self.pump_speed_str.set(self.pump_pre_speed)
        self.pump_speed_input = Entry(self.frame6, relief="groove", width=5, textvariable=self.pump_speed_str,fg=widge_attr.warning_color)



        self.pixel_size = tk.StringVar()
        self.pixel_size.set("0.33")
        self.pixel_size_field_auto = Entry(self.frame2, relief="groove", width=6, textvariable=self.pixel_size)
        self.pixel_size_field_auto.config(state=DISABLED)
        self.pixel_size_field_manual = Entry(self.frame2_2, relief="groove", width=6, textvariable=self.pixel_size)
        self.pixel_size_field_manual.config(state=DISABLED)

        self.slice_number_field_auto = Entry(self.frame1, relief="groove", width=10)
        self.slice_number_field_manual = Entry(self.frame1_1, relief="groove", width=10)

        self.account = tk.StringVar()
        self.account.set("imagestorage")
        self.account_field_auto = Entry(self.frame2, relief="groove", width=15, textvariable=self.account)
        self.account_field_auto.config(state=DISABLED)
        self.account_field_manual = Entry(self.frame2_2, relief="groove", width=15, textvariable=self.account)
        self.account_field_manual.config(state=DISABLED)

        self.server = tk.StringVar()
        self.server.set("jackw-ux1")
        self.server_field_auto = Entry(self.frame2, relief="groove", width=20, textvariable=self.server)
        self.server_field_auto.config(state=DISABLED)
        self.server_field_manual = Entry(self.frame2_2, relief="groove", width=20, textvariable=self.server)
        self.server_field_manual.config(state=DISABLED)

        self.aws = tk.StringVar()
        self.aws.set("aixin.zhang@alleninstitute.org")
        self.aws_account_field_auto = Entry(self.frame3, relief="groove", width=20, textvariable=self.aws)
        self.aws_account_field_auto.config(state=DISABLED)
        self.aws_account_field_manual = Entry(self.frame3_3, relief="groove", width=20, textvariable=self.aws)
        self.aws_account_field_manual.config(state=DISABLED)

        self.aws_pwd = tk.StringVar()
        self.aws_pwd.set("")  # Set via UI or environment variable; do not hardcode credentials
        self.aws_pwd_field_auto = Entry(self.frame3, relief="groove", width=20, textvariable=self.aws_pwd)
        self.aws_pwd_field_auto.config(state=DISABLED)
        self.aws_pwd_field_manual = Entry(self.frame3_3, relief="groove", width=20, textvariable=self.aws_pwd)
        self.aws_pwd_field_manual.config(state=DISABLED)
        ##check box
        self.mock_alignment = IntVar()
        self.mock_alignment.set(0)
        self.mock_alignment_cbox = Checkbutton(self.frame1, text="Skip Alignment",
                                               fg=widge_attr.normal_color, variable=self.mock_alignment, onvalue=1,
                                               offvalue=0)
        self.mock_alignment_cbox_manual = Checkbutton(self.frame1_1, text="Skip Alignment",
                                               fg=widge_attr.normal_color, variable=self.mock_alignment, onvalue=1,
                                               offvalue=0)

        self.build_own_cycle_sequence_value = IntVar()
        self.build_own_cycle_sequence_value.set(0)
        self.build_own_cycle_sequence = Checkbutton(self.frame1, text="Use protocol in work directory",
                                                    fg=widge_attr.normal_color,
                                                    variable=self.build_own_cycle_sequence_value,
                                                    onvalue=1,
                                                    offvalue=0)
        self.change_pixel_value = IntVar()
        self.change_pixel_value.set(0)
        self.change_pixel_auto = Checkbutton(self.frame2, text="change pixel size", command=self.change_pixel_handler_auto,
                                        fg=widge_attr.normal_color, variable=self.change_pixel_value, onvalue=1,
                                        offvalue=0)
        self.change_pixel_manual = Checkbutton(self.frame2_2, text="change pixel size",
                                             command=self.change_pixel_handler_manual,
                                             fg=widge_attr.normal_color, variable=self.change_pixel_value, onvalue=1,
                                             offvalue=0)


        self.change_server_value = IntVar()
        self.change_server_value.set(0)
        self.change_server_auto_cb = Checkbutton(self.frame2, text="change storage server",
                                              command=self.change_server_auto,
                                              fg=widge_attr.normal_color, variable=self.change_server_value, onvalue=1,
                                              offvalue=0)
        self.change_server_manual_cb = Checkbutton(self.frame2_2, text="change storage server",
                                              command=self.change_server_manual,
                                              fg=widge_attr.normal_color, variable=self.change_server_value, onvalue=1,
                                              offvalue=0)


        self.upload_aws_value = IntVar()
        self.upload_aws_value.set(0)
        self.upload_aws_auto = Checkbutton(self.frame3, text="upload to AWS", command=self.upload_to_aws_auto,
                                      fg=widge_attr.normal_color, variable=self.upload_aws_value, onvalue=1, offvalue=0)
        self.upload_aws_manual = Checkbutton(self.frame3_3, text="upload to AWS", command=self.upload_to_aws_manual,
                                           fg=widge_attr.normal_color, variable=self.upload_aws_value, onvalue=1,
                                           offvalue=0)

        self.inchamber_path = IntVar()
        self.inchamber_path.set(1)
        self.inchamber_path_cbox = Checkbutton(self.frame5, text="To chamber",
                                               fg=widge_attr.normal_color, variable=self.inchamber_path, onvalue=1,
                                               offvalue=0)

        ## Dropdown list
        self.reagent = StringVar()
        self.reagent_list_cbox = ttk.Combobox(self.frame5, textvariable=self.reagent, width=8)
        self.reagent_ls, self.reagent_dict = self.create_reagent_list()
        self.reagent_list_cbox['value'] = self.reagent_ls
        self.reagent_list_cbox['state'] = "readonly"

        self.current_c = StringVar()
        self.current_cbox = ttk.Combobox(self.frame1_1, textvariable=self.current_c, width=8)
        self.current_cbox['value'] = ['geneseq', 'hyb', 'bcseq']
        self.current_cbox['state'] = "readonly"

        ## spinner
        self.default_pump_vol = tk.DoubleVar(value=1.5)  # initial value
        self.reagent_amount = Spinbox(self.frame5, from_=1, to=10, state="readonly", increment=0.01, width=5,textvariable= self.default_pump_vol)
        self.sb1_cycle_number = Spinbox(self.frame1_1, from_=0, to=50, state="readonly", width=5)
        # canvas
        self.focusfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_focus = FigureCanvasTkAgg(self.focusfigure, master=self.frame7)
        self.alignfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_align = FigureCanvasTkAgg(self.alignfigure, master=self.frame7)
        self.tilefigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_tile = FigureCanvasTkAgg(self.tilefigure, master=self.frame7)

        ## text field
        self.note_stw = scrolledtext.ScrolledText(
            master=self.section4_addtion_note,
            wrap=tk.WORD,
            width=60,
            height=2,
        )

    # ------------------------------------------------------------------ #
    #  Delegation methods -- preserve original method signatures           #
    # ------------------------------------------------------------------ #

    # -- StatusPanel --
    def clear_focus_canvas(self):
        """Clear the focus canvas by resetting its subplot with hidden axes."""
        self._status.clear_focus_canvas()

    def clear_align_canvas(self):
        """Clear the alignment canvas by resetting its subplot with hidden axes."""
        self._status.clear_align_canvas()

    def clear_tile_canvas(self):
        """Clear the tile canvas by resetting its subplot with hidden axes."""
        self._status.clear_tile_canvas()

    def save_to_note(self):
        """Append the notes text widget content to experiment_detail.txt locally and attempt to upload it to the server."""
        self._status.save_to_note()

    def upload_aws(self):
        """Toggle the AWS upload credential fields between editable and disabled."""
        self._status.upload_aws()

    def upload_aws_handler(self):
        """Placeholder for future AWS upload functionality."""
        self._status.upload_aws_handler()

    # -- WorkspacePanel --
    def browse_handler_auto(self):
        """Open a directory chooser dialog and set the selected path in the auto tab work path field."""
        self._workspace.browse_handler_auto()

    def browse_handler_manual(self):
        """Open a directory chooser dialog and set the selected path in the manual tab work path field."""
        self._workspace.browse_handler_manual()

    def search_for_file_path(self):
        """Display a tkinter directory selection dialog and return the chosen path."""
        return self._workspace.search_for_file_path()

    def exp_btn_handler(self):
        """Open the experiment profile editor for the auto tab's work directory."""
        self._workspace.exp_btn_handler()

    def exp_btn_handler_manual(self):
        """Open the experiment profile editor for the manual tab's work directory."""
        self._workspace.exp_btn_handler_manual()

    def create_exp_auto(self):
        """Validate auto tab inputs, initialize the microscope and fluidics systems, and prepare the full automation protocol."""
        self._workspace.create_exp_auto()

    def create_exp_manual(self):
        """Validate manual tab inputs, initialize the microscope scope, and prepare for manual imaging of a single cycle."""
        self._workspace.create_exp_manual()

    # -- ExperimentConfigPanel --
    def slice_per_slide_reformat(self):
        """Parse the comma-separated slice-per-slide input from the auto tab into a list of integers."""
        self._config.slice_per_slide_reformat()

    def slice_per_slide_reformat_manual(self):
        """Parse the comma-separated slice-per-slide input from the manual tab into a list of integers."""
        self._config.slice_per_slide_reformat_manual()

    def change_pixel_handler_auto(self):
        """Toggle the pixel size entry field between editable and disabled on the auto tab."""
        self._config.change_pixel_handler_auto()

    def change_pixel_handler_manual(self):
        """Toggle the pixel size entry field between editable and disabled on the manual tab."""
        self._config.change_pixel_handler_manual()

    def change_server_auto(self):
        """Toggle the storage server fields between editable and disabled on the auto tab."""
        self._config.change_server_auto()

    def change_server_manual(self):
        """Toggle the storage server fields between editable and disabled on the manual tab."""
        self._config.change_server_manual()

    def upload_to_aws_auto(self):
        """Toggle the AWS credential fields between editable and disabled on the auto tab."""
        self._config.upload_to_aws_auto()

    def upload_to_aws_manual(self):
        """Toggle the AWS credential fields between editable and disabled on the manual tab."""
        self._config.upload_to_aws_manual()

    def assign_cycle_detail(self):
        """Read the protocol.csv file and build the ordered process list, inserting imagecycle00 if needed."""
        self._config.assign_cycle_detail()

    def check_sequence(self, n_chamber):
        """Validate all fluidics sequences in the protocol, compute total reagent volumes, and save reagents.csv."""
        self._config.check_sequence(n_chamber)

    def recipe_btn_handler(self):
        """Launch the protocol/recipe builder window for the current work directory."""
        self._config.recipe_btn_handler()

    def assign_heater(self):
        """Open a popup window to assign heat stages to individual slide chambers."""
        self._config.assign_heater()

    def assign_chamber1_heater(self):
        """Enable the heater dropdown for slide chamber 1."""
        self._config.assign_chamber1_heater()

    def assign_chamber2_heater(self):
        """Enable the heater dropdown for slide chamber 2."""
        self._config.assign_chamber2_heater()

    def assign_chamber3_heater(self):
        """Enable the heater dropdown for slide chamber 3."""
        self._config.assign_chamber3_heater()

    def assign_heater_to_slide(self):
        """Confirm the heater-to-slide assignment, store the mapping, and close the popup."""
        self._config.assign_heater_to_slide()

    # -- DevicePanel --
    def config_device(self):
        """Open a popup window that lets the user select and configure hardware device groups."""
        self._device.config_device()

    def config_dev(self):
        """Attempt to connect and configure the selected device group, updating device_status on success."""
        self._device.config_dev()

    def scan_tissue(self):
        """Launch the tissue scanner tool for the current work directory."""
        self._device.scan_tissue()

    # -- FluidicsControlPanel --
    def prime_btn_check(self):
        """Show a confirmation popup for the pump speed before priming the lines."""
        self._fluidics_ctl.prime_btn_check()

    def prime_btn_handler(self):
        """Prime all fluidics lines by running the fill-all sequence through the pump, selector, and relay."""
        self._fluidics_ctl.prime_btn_handler()

    def sensor_fluidics_process(self):
        """Poll until the fluidics cycle completes, then flush the in-chamber line with PBST and disconnect devices."""
        self._fluidics_ctl.sensor_fluidics_process()

    def create_reagent_list(self):
        """Load the reagent configuration JSON and return a list of reagent names and a name-to-address dictionary."""
        return self._fluidics_ctl.create_reagent_list()

    def fill_single_reagent(self):
        """Validate device configuration and start a background thread to pump a single reagent."""
        self._fluidics_ctl.fill_single_reagent()

    def pump_reagent(self):
        """Connect to fluidics hardware, pump the selected reagent at the specified volume and rate, then disconnect."""
        self._fluidics_ctl.pump_reagent()

    def pump_btn_check(self):
        """Show a confirmation popup for the pump speed before filling a single reagent."""
        self._fluidics_ctl.pump_btn_check()

    def wash_btn_check(self):
        """Show a confirmation popup for the pump speed before washing tubes."""
        self._fluidics_ctl.wash_btn_check()

    def wash_btn_handler(self):
        """Flush all fluidics lines with water by running the flush-all sequence."""
        self._fluidics_ctl.wash_btn_handler()

    def start_btn_check(self):
        """Show a confirmation popup for the pump speed before starting the automation sequence."""
        self._fluidics_ctl.start_btn_check()

    def start_btn_handler(self):
        """Save the calibrated pump speed, verify all devices are configured, and launch the automation sequence thread."""
        self._fluidics_ctl.start_btn_handler()

    def run_fluidics_cycle(self, sequence):
        """Load and execute a single fluidics sequence on the fluidics system."""
        self._fluidics_ctl.run_fluidics_cycle(sequence)

    # -- ImagingControlPanel --
    def focus_btn_handler(self):
        """Start the auto-focus process in a background thread (manual tab step 1)."""
        self._imaging.focus_btn_handler()

    def align_btn_handler(self):
        """Start the XY-plane alignment process in a background thread (manual tab step 2)."""
        self._imaging.align_btn_handler()

    def tile_btn_handler(self):
        """Start the tile creation process in a background thread (manual tab step 3)."""
        self._imaging.tile_btn_handler()

    def max_btn_handler(self):
        """Start the imaging and max-projection process with live view in background threads (manual tab step 4)."""
        self._imaging.max_btn_handler()

    def check_focus_file(self, path, file, msg):
        """Return 1 if the required focus file exists, otherwise log an error and return 0."""
        return self._imaging.check_focus_file(path, file, msg)

    def do_focus_thread(self):
        """Run auto-focus for the current cycle, creating DIC focus folders and plotting the focus shift results."""
        self._imaging.do_focus_thread()

    def align_and_draw_thread(self):
        """Run XY-plane alignment against cycle00 and plot the offset scatter on the alignment canvas."""
        self._imaging.align_and_draw_thread()

    def tile_and_draw_thread(self):
        """Generate image tiles for the current cycle and plot their positions on the tile canvas."""
        self._imaging.tile_and_draw_thread()

    def maxprojection_thread(self):
        """Acquire images and compute max projections for all tiles in the current cycle."""
        self._imaging.maxprojection_thread()

    def plot_live_view_thread(self):
        """Poll for newly completed max-projection tiles and display them in the live-view canvas."""
        self._imaging.plot_live_view_thread()

    def plot_maxprojection_liveview(self, name, cycle):
        """Read a max-projection TIFF, apply top-hat and denoising, convert to pseudo-color, and draw on the live-view canvas."""
        self._imaging.plot_maxprojection_liveview(name, cycle)

    def cancel_manual_process(self):
        """Signal the manual imaging process to stop."""
        self._imaging.cancel_manual_process()

    # -- AutomationController --
    def start_sequence(self):
        """Recursively execute the next step in the protocol list until all rounds complete."""
        self._automation.start_sequence()

    def image_auto(self):
        """Execute the full automated imaging pipeline: focus, align, tile, then max-project with live view."""
        self._automation.image_auto()

    def check_files(self):
        """Validate that all required input files exist before starting the automation sequence."""
        self._automation.check_files()

    def check_imagecycle00(self):
        """Verify that cycle00 position files and reference folders exist when image cycles are in the protocol."""
        self._automation.check_imagecycle00()

    def check_storage(self):
        """Check whether the max-projection disk has enough free space for the expected number of imaging rounds."""
        return self._automation.check_storage()

    def all_autobtn_disable(self):
        """Disable all primary action buttons to prevent user interaction during a running process."""
        self._automation.all_autobtn_disable()

    def all_autobtn_normal(self):
        """Re-enable all primary action buttons after a process completes or is cancelled."""
        self._automation.all_autobtn_normal()

    def write_log(self, txt):
        """Append the given text to the log.txt file in the work directory."""
        self._automation.write_log(txt)

    def cancel_btn_handler(self):
        """Cancel the running automation process by signaling all subsystems to stop and re-enabling UI buttons."""
        self.cancel=1
        self.fluidics.Heatingdevice.cancel = 1
        self.fluidics.sequenceStatus = -1
        self.fluidics.sequenceIndex = 0
        self.fluidics.cycle_done = 1
        self.fluidics.start_image = 0
        self.scope.cancel_process = 1
        txt=get_time()+"Canceled current process\n"
        add_highlight_mainwindow(txt)
        self.write_log(txt)
        self.all_autobtn_normal()
        self.cancel_sequence_btn['state'] = "disable"
