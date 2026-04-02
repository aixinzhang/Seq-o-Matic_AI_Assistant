"""Imaging control panel for the Seq-o-Matic GUI.

Handles manual-mode imaging steps: auto-focus, alignment, tiling,
max-projection, live-view plotting, and focus file checking.
"""

import os
import time
import json
import shutil
from threading import Thread

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import tifffile as tif
import cv2

from front_end.logwindow import (
    add_highlight_mainwindow, update_error, clear_error,
    update_process_bar, update_process_label, draw_liveview,
)

filterSize = (10, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, filterSize)
color_array = np.array([[0, 4, 4], [1.5, 1.5, 0], [1, 0, 1], [0, 0, 1.5]])


def _hattop_convert(x):
    """Apply a morphological top-hat transform to an image array for background subtraction."""
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)


def _denoise(x):
    """Zero out pixel values below the 85th percentile to remove low-intensity noise."""
    x[x < np.percentile(x, 85)] = 0
    return x


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


def _create_folder_file(pos_path, name):
    """Create a subdirectory under pos_path if it does not already exist."""
    if not os.path.exists(os.path.join(pos_path, name)):
        os.makedirs(os.path.join(pos_path, name))


class ImagingControlPanel:
    """Manages manual imaging steps: focus, align, tile, max-projection, and live view.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def focus_btn_handler(self):
        """Start the auto-focus process in a background thread (manual tab step 1)."""
        self.app.scope.cancel_process = 0
        clear_error()
        t = Thread(target=self.do_focus_thread)
        t.start()

    def align_btn_handler(self):
        """Start the XY-plane alignment process in a background thread (manual tab step 2)."""
        self.app.scope.cancel_process = 0
        self.app.scope.focus_status = 1
        clear_error()
        t = Thread(target=self.align_and_draw_thread)
        t.start()

    def tile_btn_handler(self):
        """Start the tile creation process in a background thread (manual tab step 3)."""
        self.app.scope.cancel_process = 0
        self.app.scope.alignment_status = 1
        clear_error()
        t = Thread(target=self.tile_and_draw_thread)
        t.start()

    def max_btn_handler(self):
        """Start the imaging and max-projection process with live view in background threads (manual tab step 4)."""
        self.app.cancel = 0
        self.app.scope.cancel_process = 0
        self.app.scope.maketiles_status = 1
        clear_error()
        df = pd.read_csv(os.path.join(self.app.pos_path, 'tiledregoffset' + self.app.current_cycle + '.csv'))
        self.app.max_name_ls = df['switched_Posinfo']
        self.app.min_x = df['X'].min() - 50
        self.app.max_x = df['X'].max() + 50
        self.app.min_y = df['Y'].min() - 50
        self.app.max_y = df['Y'].max() + 50
        t1 = Thread(target=self.maxprojection_thread)
        t1.start()
        t2 = Thread(target=self.plot_live_view_thread)
        t2.start()

    def check_focus_file(self, path, file, msg):
        """Return 1 if the required focus file exists, otherwise log an error and return 0."""
        if not os.path.exists(os.path.join(path, file)):
            txt = _get_time() + msg
            self.app.write_log(txt)
            update_error(txt)
            Pass = 0
        else:
            Pass = 1
        print(Pass)
        return Pass

    def do_focus_thread(self):
        """Run auto-focus for the current cycle, creating DIC focus folders and plotting the focus shift results."""
        if "00" in self.app.current_cycle:
            _create_folder_file(self.app.pos_path, "dicfocuscycle00")
            _create_folder_file(self.app.pos_path, "focuscycle00")
            check = self.check_focus_file(self.app.pos_path, "cycle00.pos", "Missing cycle00.pos")
            if check == 0:
                return
            else:
                self.app.focus_poslist = self.app.scope.pos_to_csv(self.app.current_cycle)
                print(self.app.focus_poslist)
                diff = self.app.scope.focus_image("cycle00", self.app.focus_poslist)
        else:
            check = self.check_focus_file(
                self.app.pos_path, "dicfocuscycle00",
                " Abort, no archor coordinates folder found!",
            )
            if check == 0:
                return
            else:
                status = self.check_focus_file(
                    self.app.pos_path, "pre_adjusted_pos.pos",
                    " Abort, no pre adjusted coordinate for current cycle!",
                )
                if status == 0:
                    return
                else:
                    _create_folder_file(self.app.pos_path, "dicfocus" + self.app.current_cycle)
                    _create_folder_file(self.app.pos_path, "focus" + self.app.current_cycle)
                    with open(os.path.join(self.app.pos_path, "pre_adjusted_pos.pos")) as f:
                        d = json.load(f)
                    shutil.copy(
                        os.path.join(self.app.pos_path, "pre_adjusted_pos.pos"),
                        os.path.join(self.app.pos_path, self.app.current_cycle + ".pos"),
                    )
                    self.app.focus_poslist = self.app.scope.pos_to_csv(self.app.current_cycle)
                    diff = self.app.scope.focus_image(self.app.current_cycle, self.app.focus_poslist)
        try:
            plot1 = self.app.focusfigure.add_subplot(111)
            plot1.plot(diff)
            plot1.axhline(y=20, color='r')
            plot1.axhline(y=-20, color='r')
            plot1.get_xaxis().set_visible(False)
            plot1.get_yaxis().set_visible(False)
            self.app.canvas_focus.draw()
            update_process_bar(0)
            update_process_label("Process")
        except Exception as e:
            txt = _get_time() + "focus is wrong or cancelled"
            update_error(txt)

    def align_and_draw_thread(self):
        """Run XY-plane alignment against cycle00 and plot the offset scatter on the alignment canvas."""
        if "00" in self.app.current_cycle:
            add_highlight_mainwindow("Cycle 00 doesn't need to run alignment!")
        else:
            self.app.scope.do_alignment(self.app.current_cycle)
            try:
                uniqslidenum = np.unique(self.app.scope.slidenum)
                print(uniqslidenum)
                data = pd.DataFrame(columns=['x', 'y', 'slidenum'])
                for i in uniqslidenum:
                    data1 = pd.DataFrame(columns=['x', 'y', 'slidenum'])
                    data1['x'] = np.round((self.app.scope.x_offset[np.where(self.app.scope.slidenum == i)]))
                    data1['y'] = np.round((self.app.scope.y_offset[np.where(self.app.scope.slidenum == i)]))
                    data1['slidenum'] = str(i)
                    data = pd.concat([data, data1], ignore_index=True)
                data.to_csv("aixintest.csv", index=False)
                print(data)
                plot2 = self.app.alignfigure.add_subplot(111)
                plot2.scatter(0, 0, marker='o')
                plot2.set(ylim=(-200, 200))
                plot2.set(xlim=(-200, 200))
                self.app.canvas_align.draw()
            except Exception as e:
                print(f"Error processing position: {e}")
                txt = _get_time() + "Aligment is wrong or cancelled" + "\n"
                update_error(txt)

    def tile_and_draw_thread(self):
        """Generate image tiles for the current cycle and plot their positions on the tile canvas."""
        self.app.scope.make_tile(self.app.current_cycle)
        txt = _get_time() + "created tiles for " + self.app.current_cycle + "\n"
        add_highlight_mainwindow(txt)
        df = pd.read_csv(os.path.join(self.app.pos_path, 'tiledregoffset' + self.app.current_cycle + '.csv'))
        plot3 = self.app.tilefigure.add_subplot(111)
        plot3.scatter(df['X'], df['Y'], c='hotpink', s=4)
        plot3.axis('scaled')
        plot3.get_xaxis().set_visible(False)
        plot3.get_yaxis().set_visible(False)
        self.app.canvas_tile.draw()

    def maxprojection_thread(self):
        """Acquire images and compute max projections for all tiles in the current cycle."""
        df = pd.read_csv(os.path.join(self.app.pos_path, 'tiledregoffset' + self.app.current_cycle + '.csv'))
        self.app.max_name_ls = df['switched_Posinfo']
        self.app.scope.image_and_maxprojection(self.app.current_cycle)

    def plot_live_view_thread(self):
        """Poll for newly completed max-projection tiles and display them in the live-view canvas."""
        name = self.app.scope.maxprojection_name
        cycle = self.app.scope.cycle
        while name != 'end' and self.app.cancel != 1 and 'imagecycle' in self.app.process_cycle:
            print(f'liveview {cycle} tile {name}')
            if name != '':
                self.plot_maxprojection_liveview(name, cycle)
            time.sleep(5)
            name = self.app.scope.maxprojection_name
        txt = _get_time() + "max_projection_finished!"
        add_highlight_mainwindow(txt)

    def plot_maxprojection_liveview(self, name, cycle):
        """Read a max-projection TIFF, apply top-hat and denoising, convert to pseudo-color, and draw on the live-view canvas."""
        disk = self.app.scope.maxprojection_drive
        img_name = name
        img = tif.imread(os.path.join(disk, self.app.pos_path[3:] + "_maxprojection", cycle, img_name))
        img_converted = np.array(list(map(_hattop_convert, img)))
        img_converted_denoise = np.array(list(map(_denoise, img_converted)))
        img_1 = np.stack(
            (
                img_converted_denoise[0, :, :],
                img_converted_denoise[1, :, :],
                img_converted_denoise[2, :, :],
                img_converted_denoise[3, :, :],
            ),
            axis=-1,
        )
        img_2 = np.reshape(img_1, (self.app.imwidth * self.app.imwidth, 4))
        img_3 = np.dot(img_2, color_array)
        img_4 = np.reshape(img_3, (self.app.imwidth, self.app.imwidth, 3))
        img_4 = np.where(img_4 > 255, 255, img_4).astype('uint8')
        draw_liveview(img_4)

    def cancel_manual_process(self):
        """Signal the manual imaging process to stop."""
        self.app.cancel = 1
        self.app.scope.cancel_process = 1
