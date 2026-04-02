"""
Tile grid generation for microscope imaging positions.

Computes tiled imaging grids from registered anchor corner positions,
with z-plane interpolation and position naming conventions.
"""
import json
import math
import os
import time

import numpy as np
import pandas as pd

from front_end.logwindow import update_error
from system.imaging.position_utils import (
    scope_constant, get_pos_data, get_col, get_row, ind2sub,
)


class TilingManager:
    """Manages tile grid generation from anchor positions for systematic imaging.

    Generates evenly spaced tile positions with configurable overlap from
    groups of 4 anchor corners, fitting z-planes via least-squares regression.
    """

    def __init__(self, parent):
        """Initialize the TilingManager with a reference to the parent ImagingSystem.

        Args:
            parent: The parent ImagingSystem instance providing core, config, and path state.
        """
        self._parent = parent

    def make_tile(self, cycle):
        """Generate the imaging tile grid after alignment completes.

        Waits for alignment to finish, loads the registered offset positions,
        generates the tile grid, fixes position naming, and saves the result.

        Args:
            cycle: Cycle name string (e.g., 'cycle01').
        """
        p = self._parent
        p.cycle = cycle
        check = p.alignment_status
        while check == 0:
            time.sleep(5)
            check = p.alignment_status
            print("Make tile thread! I am waiting alignment finished!")
        self.load_achor_regpos()
        self.createtiles()
        self.fix_Posinfo()
        p.maketiles_status=1
        print("Make tile thread! I am finished! Thread closed!")

    def load_achor_regpos(self):
        """Load the registered offset position file for the current cycle into parent.regoffset."""
        p = self._parent
        filename = 'regoffset' + p.cycle + '.pos'
        if os.path.isfile(os.path.join(p.pos_path, filename)):
            with open(os.path.join(p.pos_path, filename)) as f:
                d = json.load(f)
            if p.piezo==1:
                p.regoffset = pd.DataFrame([get_pos_data(item,p.piezo) for item in d['map']['StagePositions']['array']])[
                    ['position', 'x', 'y', 'z','piezo']]
                p.piezo_init = p.regoffset['piezo'][0]
            else:
                p.regoffset = pd.DataFrame([get_pos_data(item,p.piezo) for item in d['map']['StagePositions']['array']])[
                ['position', 'x', 'y', 'z']]
        else:
            p.regoffset = pd.DataFrame([])
        return

    def count_tiles(self):
        """Load cycle00 CSV to count tile positions (incomplete implementation)."""
        p = self._parent
        df = pd.read_csv(os.path.join(p.pos_path, 'cycle00.csv'))

    def createtiles(self):
        """Generate tiled imaging positions from registered anchor points.

        For each group of 4 anchor corners, computes the midpoint XY, fits a z-plane
        via least-squares, and generates a regular grid of tile positions with the
        configured overlap. Stores the result in parent.tilepos as a DataFrame.
        """
        p = self._parent
        df = pd.read_csv(os.path.join(p.pos_path, 'cycle00.csv'))  # this pary is used when we have piezo
        p.piezo_init = df.iloc[0]['piezo']
        tileconfig = [None] * (math.floor(len(p.regoffset) / 4))
        lablelist = []
        poslist = []
        Slide = []
        number = []
        pos = []
        for i in range(0, math.floor(len(p.regoffset) / 4)):
            y = p.regoffset['y'][i * 4:(i + 1) * 4].to_numpy(dtype=float)
            x = p.regoffset['x'][i * 4:(i + 1) * 4].to_numpy(dtype=float)
            z = p.regoffset['z'][i * 4:(i + 1) * 4].to_numpy(dtype=float)

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
                    p.imwidth * (1 - p.overlap / 100) * p.pixelsize)) + 1,
                             math.ceil(np.ptp(y) / (p.imwidth * (
                                     1 - p.overlap / 100) * p.pixelsize)) + 1]
            midpoint = [tileconfig[i][0] / 2 - 0.5, tileconfig[i][1] / 2 - 0.5]

            for n in range(0, tileconfig[i][0] * tileconfig[i][1]):
                grid_col, grid_row = ind2sub(tileconfig[i], np.array(n))
                # change LABEL
                LABEL = ['Pos' + str(i + 1) +
                         '_' + str(grid_col).zfill(3) +
                         '_' + str(grid_row).zfill(3)]
                # change XY positions
                Yoffset = (grid_row - midpoint[1]) * p.imwidth * (
                        1 - p.overlap / 100) * p.pixelsize;
                Xoffset = (grid_col - midpoint[0]) * p.imwidth * (
                        1 - p.overlap / 100) * p.pixelsize;
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

        p.tilepos = pd.DataFrame(columns=['Slidenum', 'Posinfo', 'X', 'Y', 'Z'])
        p.tilepos['Slidenum'] = Slide
        p.tilepos['Posinfo'] = lablelist
        p.tilepos['Pos'] = pos
        p.tilepos['X'] = [pos[0] for pos in poslist]
        p.tilepos['Y'] = [pos[1] for pos in poslist]
        p.tilepos['Z'] = [pos[2] for pos in poslist]
        p.maketiles_status=1

    def fix_Posinfo(self):
        """Remap tile position naming to match the expected row/column convention for downstream tools.

        Inverts the row and column indices so the naming order matches the physical
        scan direction. Saves the result as 'tiledregoffset{cycle}.csv'.
        """
        p = self._parent
        p.tilepos_new = pd.DataFrame(columns=['Slidenum', 'Posinfo', 'X', 'Y', 'Z', 'Pos', 'switched_Posinfo'])
        slice_ls = pd.unique(p.tilepos['Pos'])
        for s in slice_ls:
            image_name_df = p.tilepos[p.tilepos['Pos'] == s]
            image_name = image_name_df['Posinfo']
            col_list = [get_col(i) for i in image_name]
            row_list = [get_row(i) for i in image_name]
            row_list_new = [str(max(row_list) - i).zfill(3) for i in row_list]
            col_list_new = [str(max(col_list) - i).zfill(3) for i in col_list]
            new_name = []
            for num in range(len(row_list_new)):
                name = s + "_" + row_list_new[num] + "_" + col_list_new[num]
                new_name.append(name)
            image_name_df['switched_Posinfo'] = new_name
            frames = [p.tilepos_new, image_name_df]
            p.tilepos_new = pd.concat(frames)
        p.tilepos_new.to_csv(os.path.join(p.pos_path, 'tiledregoffset' + p.cycle + '.csv'), index=False)
