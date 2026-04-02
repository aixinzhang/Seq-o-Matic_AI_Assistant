"""Device configuration panel for the Seq-o-Matic GUI.

Handles hardware device group configuration popups and the tissue scanner launcher.
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from front_end.logwindow import widge_attr
from system.fluidics_exchange_system import FluidicSystem
from front_end.tissue_scanner import tissue_scan


class DevicePanel:
    """Manages device configuration and tissue scanning.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def config_device(self):
        """Open a popup window that lets the user select and configure hardware device groups."""
        self.app.device_popup = tk.Tk()
        self.app.device_popup.geometry("500x170")
        self.app.device_popup.title("Device config")
        self.app.device_dropdown = ttk.Combobox(self.app.device_popup, width=35)
        self.app.device_dropdown['values'] = [
            "selector group", "relay group", "heater group", "pump group",
        ]
        self.app.device_dropdown.place(x=170, y=10)
        self.app.device_label = tk.Label(
            self.app.device_popup, text="Choose system devices:", width=20,
        )
        self.app.device_label.place(x=15, y=10)
        self.app.device_config_button = tk.Button(
            self.app.device_popup, text="Config", command=self.config_dev,
        )
        self.app.device_config_button.place(x=250, y=50)
        self.app.warning_dev = scrolledtext.ScrolledText(
            master=self.app.device_popup,
            wrap=tk.WORD,
            width=60,
            height=3,
        )
        self.app.warning_dev.place(x=15, y=80)
        self.app.warning_dev.tag_config('warning', foreground="red")
        self.app.warning_dev.tag_config('normal', foreground="black")

    def config_dev(self):
        """Attempt to connect and configure the selected device group, updating device_status on success."""
        device_group = self.app.device_dropdown.get()
        self.app.pos_path = self.app.work_path_field_auto.get()
        self.app.device_status["relay_group"] = 1
        if self.app.pos_path == "":
            self.app.pos_path = "C://"
            self.app.fluidics = FluidicSystem(
                system_path=self.app.system_path,
                pos_path=self.app.pos_path,
                slide_hearter_dictionary=self.app.heater_dict,
            )
            if not os.path.exists(os.path.join(self.app.pos_path, "temp.txt")):
                open(os.path.join(self.app.pos_path, "temp.txt"), 'w')
            if not os.path.exists(os.path.join(self.app.pos_path, "log.txt")):
                open(os.path.join(self.app.pos_path, "log.txt"), 'w')
        if "pump" in device_group:
            try:
                self.app.fluidics.config_pump()
                self.app.device_status["pump_group"] = 1
                self.app.warning_dev.insert('end', "Pump groups works well!\n", 'normal')
                return
            except Exception as e:
                self.app.warning_dev.insert('end', "Please, reconnect Pump groups!\n", 'warning')
                return
        if "relay" in device_group:
            pass
        if "heater" in device_group:
            self.app.fluidics.config_heater()
            self.app.device_status["heater_group"] = 1
            self.app.warning_dev.insert('end', "Heater groups works well!\n", 'normal')
        if "selector" in device_group:
            try:
                self.app.fluidics.config_selector()
                self.app.device_status["selector_group"] = 1
                self.app.warning_dev.insert('end', "Selector groups works well!\n", 'normal')
            except Exception as e:
                self.app.warning_dev.insert('end', "Please, reconnect selector groups!\n", 'warning')
                return

    def scan_tissue(self):
        """Launch the tissue scanner tool for the current work directory."""
        scanner = tissue_scan(self.app.pos_path)
