"""
Main application window, log panels, and live view display.

Provides the LogWindow singleton class for the log/notification panel,
plus module-level helper functions for writing colored status messages,
updating the progress bar, and displaying live microscopy images.

The LogWindow must be explicitly initialized via LogWindow.initialize()
before use. Module-level functions delegate to the singleton instance.

Author: Aixin Zhang
"""
import os

import tkinter as tk
from tkinter import END, Label, PhotoImage
from tkinter import ttk, scrolledtext

import cv2
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from constants import MAIN_WINDOW_GEOMETRY


class widge_attr:
    """UI styling constants for widget appearance (colors, border widths)."""
    normal_edge = 3
    disable_edge = 0.9
    normal_color = '#0f0201'
    disable_color = '#bab8b8'
    warning_color = '#871010'
    black_color = '#0a0000'
    yellow_color = "#e0c80b"


def hattop_convert(x):
    """Apply top-hat morphological filter to enhance bright features on dark background."""
    from constants import TOPHAT_FILTER_SIZE
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, TOPHAT_FILTER_SIZE)
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)


def denoise(x):
    """Zero out pixel values below the 85th percentile (simple denoising)."""
    from constants import DENOISING_PERCENTILE
    x[x < np.percentile(x, DENOISING_PERCENTILE)] = 0
    return x


class LogWindow:
    """Singleton log/notification panel and main application window.

    Must be initialized once via LogWindow.initialize() at startup.
    Access the instance via LogWindow.get().
    """

    _instance = None

    @classmethod
    def initialize(cls):
        """Create the root Tk window and all log/status widgets.

        Must be called once at application startup before any module-level
        helper functions are used.

        Returns:
            The LogWindow singleton instance.
        """
        if cls._instance is not None:
            return cls._instance
        cls._instance = cls()
        return cls._instance

    @classmethod
    def get(cls):
        """Return the singleton instance.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if cls._instance is None:
            raise RuntimeError("LogWindow not initialized. Call LogWindow.initialize() first.")
        return cls._instance

    def __init__(self):
        """Create root window and all widgets. Do not call directly -- use initialize()."""
        self.filterSize = (10, 10)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.filterSize)
        self.color_array = np.array([[0, 4, 4], [1.5, 1.5, 0], [1, 0, 1], [0, 0, 1.5]])

        self.mainwindow = tk.Tk()
        self.mainwindow.title("Seq-o-Matic")
        self.mainwindow.geometry(MAIN_WINDOW_GEOMETRY)
        self.frame = tk.Frame(self.mainwindow, bg=self.mainwindow.cget('bg'))
        self.frame.grid(row=0, column=1, sticky="nsew")
        img = PhotoImage(file=os.path.join('LOGO.png'))
        self.mainwindow.iconphoto(False, img)

        # Warning panel (red text)
        self.warning_stw = scrolledtext.ScrolledText(
            master=self.frame, wrap=tk.WORD, width=45, height=4,
        )
        self.warning_stw.tag_config('warning', foreground="red")

        # Notification panel (multi-color text)
        self.notification_stw = scrolledtext.ScrolledText(
            master=self.frame, wrap=tk.WORD, width=45, height=10,
        )
        self.notification_stw.tag_config('highlight_from_scope', foreground='#3f51b5')
        self.notification_stw.tag_config('highlight_from_mainwindow', foreground='blue')
        self.notification_stw.tag_config('reagent_highlight_from_fluidics', foreground='#8a0788')
        self.notification_stw.tag_config('status_highlight_from_fluidics', foreground='#fcb900')
        self.notification_stw.tag_config('device_highlight_from_device', foreground='black')

        # Labels
        notification_lb = Label(self.frame, text="System Notification", bd=1, relief="groove",
                                width=15, fg=widge_attr.black_color, font=("Arial", 10))
        notification_lb.grid(row=2, column=0)

        warning_lb = Label(self.frame, text="System warning", bd=1, relief="groove",
                           width=15, fg=widge_attr.black_color, font=("Arial", 10))
        warning_lb.grid(row=0, column=0, pady=3, padx=3)

        liveview_lb = Label(self.frame, text="Live view of Barcodes", bd=1, relief="groove",
                            width=15, fg=widge_attr.black_color, font=("Arial", 10))
        liveview_lb.grid(row=5, column=0, pady=3, padx=3)

        # Progress bar
        frame1 = tk.Frame(self.frame, bg=self.mainwindow.cget('bg'))
        frame1.grid(row=3, column=0, sticky="nsew")

        self.process_lable = Label(frame1, text="Process", bd=1, relief="flat",
                                   width=18, fg=widge_attr.black_color, font=("Arial", 10))
        self.process_lable.grid(row=0, column=0, pady=3)
        self.progressbar1 = ttk.Progressbar(frame1, mode='indeterminate', length=250)
        self.progressbar1.grid(row=0, column=1, pady=3)

        # Live view figure
        self.livefigure = plt.Figure(figsize=(4, 4), dpi=100)
        self.livefigure.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.99, wspace=0, hspace=0)
        self.canvas_live = FigureCanvasTkAgg(self.livefigure, master=self.frame)
        self.canvas_live.get_tk_widget().grid(row=6, column=0, padx=3, pady=3, sticky="w")

        # Grid the text panels
        self.notification_stw.grid(row=4, column=0)
        self.warning_stw.grid(row=1, column=0)


# ---------------------------------------------------------------------------
# Backward-compatible alias: Log_window points to the LogWindow class.
# Code that accesses Log_window.mainwindow etc. will still work because
# we auto-initialize on first import (matching the old behavior).
# ---------------------------------------------------------------------------
_lw = LogWindow.initialize()

class Log_window:
    """Backward-compatible wrapper that delegates to the LogWindow singleton.

    Existing code can continue to use Log_window.mainwindow, Log_window.warning_stw, etc.
    """
    mainwindow = _lw.mainwindow
    frame = _lw.frame
    warning_stw = _lw.warning_stw
    notification_stw = _lw.notification_stw
    process_lable = _lw.process_lable
    progressbar1 = _lw.progressbar1
    livefigure = _lw.livefigure
    canvas_live = _lw.canvas_live
    filterSize = _lw.filterSize
    kernel = _lw.kernel
    color_array = _lw.color_array


# ---------------------------------------------------------------------------
# Module-level helper functions (delegate to singleton)
# ---------------------------------------------------------------------------

def update_error(txt):
    """Append red warning text to the warning panel."""
    LogWindow.get().warning_stw.insert(END, txt, 'warning')

def clear_error():
    """Clear all text from the warning panel."""
    LogWindow.get().warning_stw.delete('1.0', tk.END)

def clear_log():
    """Clear all text from the notification panel."""
    LogWindow.get().notification_stw.delete('1.0', tk.END)

def add_highlight_from_scope(txt):
    """Add scope-origin message to notification panel (blue)."""
    LogWindow.get().notification_stw.insert(END, txt, 'highlight_from_scope')

def add_device_information(txt):
    """Add device info message to notification panel (black)."""
    LogWindow.get().notification_stw.insert(END, txt, 'device_highlight_from_device')

def add_fluidics_status(txt):
    """Add fluidics status message to notification panel (yellow)."""
    LogWindow.get().notification_stw.insert(END, txt, 'status_highlight_from_fluidics')

def add_fluidics_reagent(txt):
    """Add fluidics reagent message to notification panel (purple)."""
    LogWindow.get().notification_stw.insert(END, txt, 'reagent_highlight_from_fluidics')

def add_highlight_mainwindow(txt):
    """Add main window message to notification panel (blue)."""
    LogWindow.get().notification_stw.insert(END, txt, 'highlight_from_mainwindow')

def update_process_bar(i):
    """Set the progress bar value (0-100)."""
    LogWindow.get().progressbar1['value'] = i

def update_process_label(txt):
    """Update the label text next to the progress bar."""
    LogWindow.get().process_lable['text'] = txt

def draw_liveview(img):
    """Display a cropped center region of an image in the live view canvas."""
    lw = LogWindow.get()
    plot1 = lw.livefigure.add_subplot(111)
    plot1.imshow(img[500:1200, 500:1200, :])
    plot1.get_xaxis().set_visible(False)
    plot1.get_yaxis().set_visible(False)
    lw.canvas_live.draw()

def clear_liveview_canvas():
    """Reset the live view canvas to a blank figure."""
    lw = LogWindow.get()
    lw.livefigure = plt.Figure(figsize=(4, 4), dpi=100)
    lw.livefigure.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.99, wspace=0, hspace=0)
    lw.canvas_live = FigureCanvasTkAgg(lw.livefigure, master=lw.frame)
