"""
Standalone utility functions for microscope position management, file handling,
and image preprocessing.

Extracted from the original image_acquisition_and_analysis_system module.
"""
import copy
import json
import math
import os
import shutil
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
from pytz import timezone


class scope_constant():
    """Hardware constants for microscope imaging parameters.

    Stores default piezo focus range, step sizes, sharpening kernel,
    and other imaging constants used throughout the acquisition pipeline.
    These values define the z-stack sweep ranges for both focusing and
    max-projection acquisition modes.
    """

    piezo_focus_start_pos = -40
    piezo_focus_end_pos = 40
    piezo_step = 1.5

    # scope_start_pos = -15
    # scope_end_pos = 15
    # scope_focus_end_pos = 30
    # scope_focus_start_pos = -30
    # scope_step = 1.5

    piezo_maxpro_start_pos = -15
    piezo_maxpro_end_pos = 15
    sharpen1 = np.array(([0, 1, 0],
                         [-1, 5, -1],
                         [0, -1, 0]), dtype="int")
    pos_per_slice = 4;
    z_dir=1


def get_file_name(path, kind):
    """Return a list of filenames in the given directory that end with the specified extension.

    Args:
        path: Directory path to search in.
        kind: File extension to filter by (e.g., '.tif').

    Returns:
        List of matching filenames.
    """
    files = []
    for file in os.listdir(path):
        if file.endswith(kind):
            files.append(file)
    return files


def sort_by(string):
    """Sort a list of TIFF filenames by their position number extracted from the 'PosN.tif' pattern.

    Args:
        string: List of filenames containing 'PosN.tif' naming convention.

    Returns:
        List of filenames sorted in ascending position number order.
    """
    pos = np.array([int(s[s.find('Pos') + 3:s.find('.tif')]) for s in string])
    rearrange = np.argsort(pos)
    string = [string[i] for i in rearrange]
    return string

def clean_space(directory):
    """Remove all subdirectories within the given directory, leaving files intact."""
    for item in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, item)):
            shutil.rmtree(os.path.join(directory, item))

def get_time():
    """Return the current US/Pacific time as a formatted string (YYYY-MM-DD HH:MM:SS) with newline."""
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time


def get_col(image_file_name):
    """Extract the column index from a tile image filename (e.g., 'Pos1_003_002.tif' -> 3)."""
    start = image_file_name.find('_', 7) + 1
    end = start + 3
    return int(image_file_name[start:end])


def get_row(image_file_name):
    """Extract the row index from a tile image filename (e.g., 'Pos1_003_002.tif' -> 3 from first underscore group)."""
    start = image_file_name.find('_') + 1
    end = start + 3
    return int(image_file_name[start:end])


def copy_dic(pos_path, focusfolder, dicfolder):
    """Move all TIFF files from the focus folder to the DIC (differential interference contrast) folder.

    Args:
        pos_path: Base path for position data.
        focusfolder: Source subfolder containing focus images.
        dicfolder: Destination subfolder for DIC images.
    """
    directory = os.listdir(os.path.join(pos_path, focusfolder))
    for i in directory:
        if ".tif" in i:
            shutil.move(os.path.join(pos_path, focusfolder, i),
                        os.path.join(pos_path, dicfolder, i))


def ind2sub(array_shape, ind):
    """Convert linear indices to row/column subscripts, replicating MATLAB's ind2sub behavior.

    Args:
        array_shape: Tuple of (num_rows, num_cols) defining the grid dimensions.
        ind: Linear index (or array of indices) to convert.

    Returns:
        Tuple of (rows, cols) corresponding to the linear index in column-major order.
    """
    cols = (ind.astype("int32") // array_shape[0])
    rows = (ind.astype("int32") % array_shape[0])
    return (rows, cols)


def save_offset_and_json(pos_path, file, dict, jsonfile,z_dir):
    """Save focus z-offsets to CSV and update the Micro-Manager position JSON file.

    Computes z-shift from piezo focus offsets, updates both the CSV position list
    and the JSON stage position file with corrected z values. Also writes
    'pre_adjusted_pos.pos' for microscope use.

    Args:
        pos_path: Base directory for position files.
        file: CSV filename with position data.
        dict: Dictionary mapping position names (e.g., 'Pos0') to new z-offset values.
        jsonfile: Micro-Manager .pos JSON filename to update.
        z_dir: Z direction multiplier (+1 or -1) for offset correction.

    Returns:
        Array of z-shift differences (in micrometers) for each position.
    """
    pos_list = pd.read_csv(os.path.join(pos_path, file))
    for i in range(len(pos_list)):
        pos_list.loc[pos_list['position'] == 'Pos' + str(i), ['z_offset']] = dict['Pos' + str(i)]
    #pos_list['z_shift']=(pos_list['z_offset']-pos_list['z'])/1.5 # This is used if we don't have piezo
    pos_list['z_shift']=(pos_list['piezo']-pos_list['z_offset'])/1.5  # This is used if we  have piezo
    pos_list['z_offset'] = pos_list['z']+pos_list['z_shift']*z_dir*(1.5)# This is used if we  have piezo
    pos_list.to_csv(os.path.join(pos_path, "offset" + file))
    with open(os.path.join(pos_path, jsonfile)) as f:
        d = json.load(f)
    d2 = copy.deepcopy(d)
    for i in pos_list.index:
        d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][0]['Position_um']['array'][0] = \
            pos_list.loc[
                i, 'z_offset']
    json_object = json.dumps(d2, indent=2)
    with open(os.path.join(pos_path, "offset" + jsonfile), "w") as outfile:
        outfile.write(json_object)

    with open(os.path.join(pos_path, "pre_adjusted_pos.pos"), "w") as outfile:
        outfile.write(json_object)
    diff = pos_list['z_shift'].values * 1.5
    return diff


def get_pos_data(item,piezo):
    """Extract position data (x, y, z, and optionally piezo) from a Micro-Manager stage position entry.

    Args:
        item: A single stage position dictionary from the Micro-Manager .pos JSON format.
        piezo: Flag (1 = piezo present, 0 = no piezo) controlling which position parser to use.

    Returns:
        Dictionary with keys 'position', 'x', 'y', 'z' (and 'piezo' if piezo=1).
    """
    positions = item['DevicePositions']['array']
    pos_data = {}
    if piezo==1:
        for pos in positions:
            pos_data.update(get_position_piezo(pos))
        pos_data.update({'position': item['Label']['scalar']})
    else:
        for pos in positions:
            pos_data.update(get_position(pos))
        pos_data.update({'position': item['Label']['scalar']})
    return pos_data


def get_position_piezo(pos):
    """Parse a single device position entry and return a dict with z, x/y, or piezo values.

    Handles ZDrive, XYStage, and DA Z Stage (piezo) device types.

    Args:
        pos: Device position dictionary with 'Device' and 'Position_um' keys.

    Returns:
        Dictionary with the device-specific coordinate(s), or None for unknown devices.
    """
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

def get_position(pos):
    """Parse a single device position entry and return a dict with z or x/y values (no piezo).

    Handles ZDrive and XYStage device types only.

    Args:
        pos: Device position dictionary with 'Device' and 'Position_um' keys.

    Returns:
        Dictionary with the device-specific coordinate(s), or None for unknown devices.
    """
    position_name = pos['Device']['scalar']
    position_value = pos['Position_um']['array']
    if position_name == 'ZDrive':
        return {'z': position_value[0]}
    elif position_name == 'XYStage':
        return {'x': position_value[0], 'y': position_value[1]}
    else:
        return None

filterSize =(10, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT,  filterSize)
color_array=np.array([[0,4,4],[1.5,1.5,0],[1,0,1],[0,0,1.5]])

def hattop_convert(x):
    """Apply a morphological top-hat transform to enhance bright structures on a dark background."""
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)

def denoise(x):
    """Zero out pixel values below the 85th percentile as a simple thresholding denoise."""
    x[x<np.percentile(x, 85)]=0
    return x


def single_createtiles(df,imwidth,overlap,pixelsize):
    """Generate a tiled grid of imaging positions from groups of 4 anchor corner points.

    For each group of 4 anchor positions, computes the midpoint, fits a z-plane via
    least-squares regression, and generates a grid of evenly spaced tile positions
    with the specified overlap. Each tile receives interpolated X, Y, Z coordinates.

    Args:
        df: DataFrame with columns 'x', 'y', 'z' containing anchor positions.
        imwidth: Image width in pixels.
        overlap: Tile overlap percentage (0-100).
        pixelsize: Physical pixel size in micrometers per pixel.

    Returns:
        DataFrame with columns 'Slidenum', 'Posinfo', 'Pos', 'X', 'Y', 'Z' for all tiles.
    """
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
                imwidth * (1 -overlap / 100) * pixelsize)) + 1,
                         math.ceil(np.ptp(y) / (imwidth * (
                                 1 - overlap / 100) * pixelsize)) + 1]
        midpoint = [tileconfig[i][0] / 2 - 0.5, tileconfig[i][1] / 2 - 0.5]

        for n in range(0, tileconfig[i][0] * tileconfig[i][1]):
            grid_col, grid_row = ind2sub(tileconfig[i], np.array(n))
            # change LABEL
            LABEL = ['Pos' + str(i + 1) +
                     '_' + str(grid_col).zfill(3) +
                     '_' + str(grid_row).zfill(3)]
            # change XY positions
            Yoffset = (grid_row - midpoint[1]) * imwidth * (
                    1 - overlap / 100) * pixelsize;
            Xoffset = (grid_col - midpoint[0]) * imwidth * (
                    1 - overlap / 100) * pixelsize;
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
