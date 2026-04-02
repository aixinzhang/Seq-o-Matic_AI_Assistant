"""Tissue scanner module for automated microscope slide scanning and stitching.

This module provides tools for scanning tissue slides using a microscope controlled
via pycromanager (Micro-Manager). It includes constants for microscope configuration,
functions for computing tile positions and stitching images, and a Tkinter-based GUI
for interactive slide scanning and coordinate selection. The workflow involves defining
slide edge positions, generating a tiled acquisition grid, acquiring images, stitching
them into an overview, and allowing the user to click on the overview to select
positions of interest for downstream analysis.
"""

import tkinter as tk
from tkinter import ttk
import os
import pandas as pd
import json
from datetime import datetime
from pytz import timezone
import math
from pycromanager import Core
import numpy as np
import cv2
from pycromanager import Acquisition, multi_d_acquisition_events
from PIL import ImageTk, Image
import shutil
import tifffile as tiff
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, StringVar,filedialog,messagebox,scrolledtext,Button

import copy


class scope_constant():
    """Microscope hardware constants and imaging parameters.

    Stores default positions, step sizes, exposure times, and image geometry
    used throughout the tissue scanning pipeline. All values are class-level
    attributes shared across the application.
    """

    piezo_focus_start_pos = -30
    piezo_focus_end_pos = 30
    piezo_step = 1.5

    scope_start_pos = -15
    scope_end_pos = 15
    scope_focus_end_pos = 30
    scope_focus_start_pos = -30
    scope_step = 1.5

    piezo_maxpro_start_pos = -15
    piezo_maxpro_end_pos = 15

    ZDrive_safe_pos = 500
    XYStage_fluidics_safe_pos = [-56900.7, -3062.1]
    XYStage_image_safe_pos = [44198.6, -4834.5]

    scope_exposure_time_dict = {"G": 220, "T": 150, "A": 100, "C": 100, "DIC": 10, "GFP": 100, "TxRed": 100, "DAPI": 50}
    stack_num_focus = round(abs(piezo_focus_end_pos - piezo_focus_start_pos) / piezo_step)
    stack_num_maxpro = round(abs(piezo_maxpro_start_pos - piezo_maxpro_end_pos) / piezo_step)

    sharpen1 = np.array(([0, 1, 0],
                         [-1, 5, -1],
                         [0, -1, 0]), dtype="int")
    stage_x_dir = -1;  # -1: left is larger
    stage_y_dir = 1;  # 1: bottom is larger
    pos_per_slice = 4;
    pixelsize =0.33
    imwidth =3200
    overlap = 0

def get_position_piezo(pos):
    position_name = pos['Device']['scalar']
    position_value = pos['Position_um']['array']
    if position_name == 'ZDrive':
        return {'z': position_value[0]}
    elif position_name == 'XYStage':
        return {'x': position_value[0], 'y': position_value[1]}
    elif position_name == 'DA Z Stage':
        return {'piezo': position_value[0]}
    else:
        pass
def ind2sub(array_shape, ind):
    # Gives repeated indices, replicates matlabs ind2sub
    cols = (ind.astype("int32") // array_shape[0])
    rows = (ind.astype("int32") % array_shape[0])
    return (rows, cols)
def get_pos_data(item):
    positions = item['DevicePositions']['array']
    pos_data = {}
    for pos in positions:
        pos_data.update(get_position_piezo(
            pos))  # change to get_position_piezo(pos) if have piezo, change to get_position(pos) if no piezo
    pos_data.update({'position': item['Label']['scalar']})
    return pos_data
def createtiles(df):
    tileconfig = [None] * (math.floor(len(df) / 4))
    lablelist = []
    poslist = []
    Slide = []
    number = []
    pos = []
    for i in range(0, math.floor(len(df) / 4)):
        y = df['y'][i * 4:(i + 1) * 4].to_numpy(dtype=float)
        x = df['x'][i * 4:(i + 1) * 4].to_numpy(dtype=float)
        z = df['z'][i * 4:(i + 1) * 4].to_numpy(dtype=float)

        # calculate midpoint xy
        midpointx = np.ptp(x) / 2 + np.min(x)
        midpointy = np.ptp(y) / 2 + np.min(y)
        # regress z slope and midpoint on xy
        a = np.array([x - midpointx, y - midpointy, np.ones(len(x))])
        z1 = np.linalg.lstsq(a.T, np.array([z]).T, rcond=None)[0]
        zslopex = z1[0];
        zslopey = z1[1];
        midpointz = z1[2];
        # calculate tile config
        tileconfig[i] = [math.ceil(np.ptp(x) / (
                scope_constant.imwidth * (1 - scope_constant.overlap / 100) * scope_constant.pixelsize)) + 1,
                         math.ceil(np.ptp(y) / (scope_constant.imwidth * (
                                 1 - scope_constant.overlap / 100) * scope_constant.pixelsize)) + 1]
        midpoint = [tileconfig[i][0] / 2 - 0.5, tileconfig[i][1] / 2 - 0.5]

        for n in range(0, tileconfig[i][0] * tileconfig[i][1]):
            grid_col, grid_row = ind2sub(tileconfig[i], np.array(n))
            # change LABEL
            LABEL = ['Pos' + str(i + 1) +
                     '_' + str(grid_col).zfill(3) +
                     '_' + str(grid_row).zfill(3)]
            # change XY positions
            Yoffset = (grid_row - midpoint[1]) * scope_constant.imwidth * (
                    1 - scope_constant.overlap / 100) * scope_constant.pixelsize;
            Xoffset = (grid_col - midpoint[0]) * scope_constant.imwidth * (
                    1 - scope_constant.overlap / 100) * scope_constant.pixelsize;
            Y = round(midpointy + Yoffset);
            X = round(midpointx + Xoffset);
            # find the device of XYstage
            Zoffset = Yoffset * zslopey + Xoffset * zslopex;
            Z = midpointz + Zoffset;
            poslist.append([X, Y, Z[0]])
            lablelist.append(LABEL[0])
            Slide.append('slide_' + str(i + 1))
            pos.append('Pos' + str(i + 1))
            number.append(n)

    tilepos = pd.DataFrame(columns=['Slidenum', 'Posinfo', 'X', 'Y', 'Z'])
    tilepos['Slidenum'] = Slide
    tilepos['Posinfo'] = lablelist
    tilepos['Pos'] = pos
    tilepos['X'] = [pos[0] for pos in poslist]
    tilepos['Y'] = [pos[1] for pos in poslist]
    tilepos['Z'] = [pos[2] for pos in poslist]
    return tilepos
def get_col(image_file_name):
    start = image_file_name.find('_', 7) + 1
    end = start + 3
    return int(image_file_name[start:end])


def get_row(image_file_name):
    start = image_file_name.find('_') + 1
    end = start + 3
    return int(image_file_name[start:end])
def fix_Posinfo(tilepos):
    tilepos_new = pd.DataFrame(columns=['Slidenum', 'Posinfo', 'X', 'Y', 'Z', 'Pos', 'switched_Posinfo'])
    slice_ls = pd.unique(tilepos['Pos'])
    for s in slice_ls:
        image_name_df = tilepos[tilepos['Pos'] == s]
        image_name = image_name_df['Posinfo']
        col_list = [get_col(i) for i in image_name]
        row_list = [get_row(i) for i in image_name]
        row_list_new = [str(i).zfill(3) for i in row_list]
        col_list_new = [str(max(col_list) - i).zfill(3) for i in col_list]
        new_name = []
        for num in range(len(row_list_new)):
            name = s + "_" + row_list_new[num] + "_" + col_list_new[num]
            new_name.append(name)
        image_name_df['switched_Posinfo'] = new_name
        frames = [tilepos_new, image_name_df]
        tilepos_new = pd.concat(frames)
        tilepos_new.to_csv('test_only.csv')
        return tilepos_new
def create_scan_even(XY):
    event = []
    for i in range(XY.shape[0]):
        event.append({'axes': {'channel': 'DIC'},'config_group': ['Channel', 'DIC'],'exposure':10,'X':XY[i][0],'Y':XY[i][1]})
    return event

class tissue_scan():
    """GUI controller for scanning tissue slides on the microscope.

    Provides a Tkinter popup window that lets the user select a slide,
    set a Z-plane, trigger an automated tiled acquisition, stitch the
    resulting images into an overview, and open an interactive coordinate
    selector for choosing positions of interest.
    """

    def __init__(self,path):
        """Initialize the tissue scan GUI.

        Args:
            path: Base directory path for saving output position files.
        """
        self.path=path
        self.core=Core()
        self.coordinate=[]
        self.scan_popup = tk.Tk()
        self.scan_popup.title("Scan slides")
        self.scan_popup.geometry("680x120")
        self.dropdown = ttk.Combobox(self.scan_popup, width=25)
        self.dropdown['values'] = ['slide1','slide2','slide3']
        self.dropdown.place(x=90,y=10)
        self.scale_factor=0.1
        self.tile_width = round(3200*self.scale_factor)
        self.tile_height = round(3200*self.scale_factor)

        self.scan_button = tk.Button(self.scan_popup, text="Scan slide", command=self.scan_slide,width=20)
        self.scan_button.place(x=510, y=10)
        self.label1=tk.Label(self.scan_popup,text="Choose slide:",width=10)
        self.label1.place(x=2, y=10)
        self.label3 = tk.Label(self.scan_popup, text="Combine slides:", width=13)
        self.label3.place(x=2, y=55)
        self.slide_number_field = tk.Entry(self.scan_popup, relief="groove", width=10)
        self.slide_number_field.place(x=100, y=55)
        self.label2 = tk.Label(self.scan_popup, text="Z-plane:", width=10)
        self.label2.place(x=270, y=10)
        self.z_plane = tk.StringVar()
        self.z_plane.set(3228)
        self.z_plane_field = tk.Entry(self.scan_popup, relief="groove", width=10, textvariable=self.z_plane)
        self.z_plane_field.place(x=350, y=10)
        self.combine_button = tk.Button(self.scan_popup, text="Combine slide edge positions", command=self.combine_pos, width=25)
        self.combine_button.place(x=200, y=55)

    def combine_pos(self):
        """Combine edge positions from multiple slides into a single .pos file.

        Reads auto.csv files from each slide directory specified in the combine
        slides entry field, merges them, and writes a combined Micro-Manager
        position list to the output path.
        """
        a = self.slide_number_field.get()
        print(a)
        slide_num = ["slide"+x for x in a.split(',')]
        df_whole=pd.DataFrame()
        for i in slide_num:
            df=pd.read_csv(os.path.join("device", "tissue_scanner", i,"auto.csv"))
            df_whole=pd.concat([df_whole,df])
        with open(os.path.join("device", "tissue_scanner", "template.pos")) as f:
            temp = json.load(f)
        temp_coor = temp['map']['StagePositions']['array'][0]
        temp['map']['StagePositions']['array'] = copy.deepcopy([])
        for i in range(len(df_whole)):
            temp_coor['DevicePositions']['array'][2]['Position_um']['array'] = copy.deepcopy(
                [int(df_whole.iloc[i, 0]), int(df_whole.iloc[i, 1])])
            temp_coor['Label']['scalar'] = copy.deepcopy('Pos' + str(i))
            temp['map']['StagePositions']['array'].append(copy.deepcopy(temp_coor))
        json_object = json.dumps(temp, indent=2)
        with open(os.path.join(self.path, "auto.pos"), "w") as outfile:
            outfile.write(json_object)
    def run_scope(self,slide):
        """Execute the tiled microscope acquisition for the given slide.

        Moves the Z-drive to the configured Z-plane, builds acquisition events
        for all XY tile positions, and runs a pycromanager Acquisition that
        saves images into the slide's directory.

        Args:
            slide: Name of the slide subdirectory (e.g. 'slide1').
        """
        if os.path.exists(os.path.join("device", "tissue_scanner", slide,"stack_1")):
            shutil.rmtree(os.path.join("device", "tissue_scanner", slide,"stack_1"))
        self.z=int(self.z_plane_field.get())
        self.core.set_position("ZDrive",self.z)
        self.scan_event = []
        self.channel = []

        for i in range(0, len(self.xy_positions)):
            self.scan_event.append({'axes': {'position':i},
                                    'x':self.xy_positions[i][0],
                                    'y': self.xy_positions[i][1],
                                'config_group': ['Channel', "Hyb-DAPI"],
                                'exposure': 20,
                                })
        with Acquisition(directory=os.path.join("device", "tissue_scanner", slide), name="stack",
                         show_display=False) as acq:
           acq.acquire(self.scan_event)
        print("image done!")

    def stich_image(self,slide):
        """Stitch acquired tile images into a single downscaled overview.

        Reads all tile TIFF images from the acquisition directory, arranges them
        into a grid, applies CLAHE contrast enhancement, and saves the result as
        'stitched_image_check.tif'.

        Args:
            slide: Name of the slide subdirectory containing the acquired stack.
        """
        print("Stitch!")
        img_list = [i for i in os.listdir(os.path.join("device", "tissue_scanner", slide, 'stack_1')) if ".tif" in i]
        img = tiff.imread(os.path.join("device", "tissue_scanner", slide, 'stack_1', img_list[0]))
        self.stitched_image = np.zeros((self.row * self.tile_height, self.col * self.tile_width), dtype=np.uint8)
        for i in range(self.row):
            for j in range(self.col):
                #index = (self.row - i - 1) * self.col + j
                index = i  * self.col + (self.col-j-1)
                image = cv2.resize(img[index, :, :], None, fx=self.scale_factor, fy=self.scale_factor)
                x = j * self.tile_width
                y = i * self.tile_height
                image=cv2.flip(image, -1)
                self.stitched_image[y:y + self.tile_height, x:x + self.tile_width] = image
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(self.stitched_image)
        self.stitched_image_rt = enhanced
        tiff.imwrite(os.path.join("device", "tissue_scanner",slide,"stitched_image_check.tif"), self.stitched_image_rt)


    def scan_slide(self):
        """Orchestrate the full slide scanning workflow.

        Loads the slide position file, computes tile positions, runs the
        microscope acquisition, stitches the overview image, and opens an
        interactive coordinate collector window for the user to select
        positions of interest.
        """
        self.slide=self.dropdown.get()
        with open(os.path.join("device", "tissue_scanner", self.slide,"slide.pos")) as f:
            self.temp1 = json.load(f)
        df = pd.DataFrame([get_pos_data(item) for item in self.temp1['map']['StagePositions']['array']])[
            ['position', 'x', 'y', 'z', 'piezo']]
        tiles = createtiles(df)
        self.tiles = fix_Posinfo(tiles)
        self.xy_positions = self.tiles[["X", "Y"]].to_numpy()
        self.col = max([get_row(i) for i in self.tiles['Posinfo']]) + 1
        self.row = max([get_col(i) for i in self.tiles['Posinfo']]) + 1
        self.run_scope(self.slide)
        self.stich_image(self.slide)
        self.subwindow = tk.Tk()
        self.subwindow.geometry("400x1000")
        collector = ImageCoordinateCollector(self.subwindow, self.stitched_image,self.stitched_image_rt,self.path,self.tile_width,self.tiles,self.z,self.slide)
        del self.stitched_image
        del self.stitched_image_rt
        self.subwindow.mainloop()







class ImageCoordinateCollector:
    """Interactive GUI for selecting positions on a stitched slide overview image.

    Displays the stitched overview in a Matplotlib canvas embedded in a Tkinter
    window. The user clicks on the image to mark positions of interest, which are
    then mapped back to original microscope stage coordinates and saved as a CSV
    file for downstream automated imaging.
    """

    def __init__(self, window, stitched_image,stitched_image_rt,path,width,tilesdf,z,slide):
        """Initialize the coordinate collector GUI.

        Args:
            window: Parent Tkinter window.
            stitched_image: Raw stitched overview image array.
            stitched_image_rt: Contrast-enhanced stitched image for display.
            path: Base output directory for position files.
            width: Tile width in pixels (after scaling).
            tilesdf: DataFrame of tile positions with columns Posinfo, X, Y.
            z: Z-drive position used during the scan.
            slide: Name of the slide subdirectory.
        """
        self.window = window
        self.image=stitched_image
        self.slide=slide
        self.window.title("Image Coordinate Collector")
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_columnconfigure(1, weight=1)
        self.pos_path=path
        self.tile_width=width
        self.tilesdf=tilesdf
        self.fig, self.ax = plt.subplots()
        self.fig.tight_layout(pad=0)
        self.stitch_image=stitched_image
        self.stitch_image_rt=stitched_image_rt
        self.ax.imshow(self.stitch_image_rt, cmap="Greys")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.window)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.canvas.draw()
        self.coordinates = []
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.print_button = tk.Button(self.window, text="Save Coordinates", command=self.save_coordinates)
        self.print_button.grid(row=1, column=0)
        self.clear_button = tk.Button(self.window, text="Clear Points", command=self.clear_points)
        self.clear_button.grid(row=1, column=1)
        self.Z=z


    def on_click(self, event):
        """Handle mouse click events on the image canvas.

        Records the clicked pixel coordinate and draws a red 'x' marker at
        that location on the displayed image.
        """
        if event.inaxes is not None:
            x, y = event.xdata, event.ydata
            self.coordinates.append((x, y))
            self.ax.plot(x, y, marker='x', color='red', markersize=10)
            self.canvas.draw()
    def find_original_coor(self,XY):
        """Convert pixel coordinates from the stitched overview to stage coordinates.

        Maps each clicked (x, y) pixel position back to the corresponding tile
        in the tile grid and looks up its original microscope XY stage position.

        Args:
            XY: List of (x, y) pixel coordinate tuples from the stitched image.

        Returns:
            Numpy array of shape (N, 2) with original stage [X, Y] coordinates.
        """
        coor = []
        for i in range(len(XY)):
            X = XY[i][0]
            Y = XY[i][1]
            row = math.floor(Y / self.tile_width)
            col=max([get_row(i) for i in self.tilesdf['Posinfo']])-math.floor(X / self.tile_width) #flip image

            name = "Pos1_" + str(col).zfill(3) + "_" + str(row).zfill(3)
            coor.append([self.tilesdf.loc[self.tilesdf["Posinfo"] == name]['X'].iloc[0],
                        self.tilesdf.loc[self.tilesdf["Posinfo"] == name]['Y'].iloc[0]])
        coor=np.array(coor)
        return coor
    def save_coordinates(self):
        """Save the selected coordinates to a CSV file and close the window.

        Converts the clicked pixel positions to original stage coordinates,
        writes them to 'auto.csv' in the slide directory, and destroys the
        collector window.
        """
        self.ori_coor=self.find_original_coor(self.coordinates)
        df =pd.DataFrame( {'X': self.ori_coor[:,0], 'Y': self.ori_coor[:,1]})
        df.to_csv(os.path.join("device", "tissue_scanner", self.slide,"auto.csv"),index=False)
        messagebox.showinfo(title="Save", message="auto position is saved!")
        del self.stitch_image
        del self.stitch_image_rt
        self.window.destroy()


    def clear_points(self):
        """Remove all marked points and redraw the clean overview image."""
        self.coordinates.clear()
        self.ax.clear()
        self.ax.imshow(self.stitch_image_rt, cmap="Greys")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()
