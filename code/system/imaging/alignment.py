"""
Image alignment (registration) for cycle-to-cycle offset correction.

Uses phase correlation (FFT-based) to compute sub-pixel XY translations
between reference and current cycle DIC focus images.
"""
import copy
import json
import math
import os
import threading
import time

import cv2
import numpy as np
import pandas as pd

from front_end.logwindow import (
    update_error, add_highlight_from_scope,
    update_process_bar, update_process_label,
)
from system.imaging.position_utils import (
    scope_constant, get_time, sort_by, get_pos_data,
)


class AlignmentManager:
    """Manages image registration between sequencing cycles using phase correlation.

    Computes XY translation offsets between cycle00 reference images and current
    cycle images, pools offsets per slide, performs sanity checks, and updates
    position files with corrected coordinates.
    """

    def __init__(self, parent):
        """Initialize the AlignmentManager with a reference to the parent ImagingSystem.

        Args:
            parent: The parent ImagingSystem instance providing core, config, and path state.
        """
        self._parent = parent

    def do_alignment(self, cycle):
        """Perform image registration (alignment) between cycle00 and the current cycle.

        If mock_align is enabled, skips alignment and writes identity-transform offset files.
        Otherwise, waits for focusing to complete, loads reference and current DIC images,
        and computes XY translation offsets via phase correlation (imregcorr).

        Args:
            cycle: Cycle name string to align against cycle00.
        """
        p = self._parent
        if p.mock_align==1:
            p.cycle = cycle
            p.pos_batch_size = [i * scope_constant.pos_per_slice for i in p.slicePerSlide]
            print(p.pos_batch_size)
            p.slidenum = np.zeros(sum(p.pos_batch_size))
            p.x_offset = np.zeros(p.pos_batch_size)
            p.y_offset = np.zeros(p.pos_batch_size)
            df = pd.read_csv(os.path.join(p.pos_path, 'offset' + p.cycle + '.csv'))
            df['x_adjust'] = df['x']
            df['y_adjust'] = df['y']
            df.to_csv(os.path.join(p.pos_path, 'regoffset' + p.cycle + '.csv'), index=False)
            filename = 'offset' + p.cycle + ".pos"
            new_filename = 'regoffset' + p.cycle + '.pos'
            with open(os.path.join(p.pos_path, filename)) as f:
                d = json.load(f)
            d2 = copy.deepcopy(d)
            for i in df.index:
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][2]['Position_um']['array'][0] = \
                df.loc[
                    i, 'x_adjust']
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][2]['Position_um']['array'][1] = \
                df.loc[
                    i, 'y_adjust']
            # switch to d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][2] if you have piezo,d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][1] if no piezo
            json_object = json.dumps(d2, indent=2)
            with open(os.path.join(p.pos_path, new_filename), "w") as outfile:
                outfile.write(json_object)
            with open(os.path.join(p.pos_path, "pre_adjusted_pos.pos"), "w") as outfile:
                outfile.write(json_object)
            txt = get_time() + p.cycle + " saved regoffset.pos for microscope review and next cycle\n"
            add_highlight_from_scope(txt)
            p.write_log(txt)
            print("saved regoffset.pos for microscope review and next cycle")
            p.alignment_status = 1
            return
        else:
            check_focus = p.focus_status
            p.cycle = cycle
            while check_focus == 0 and p.cancel_process!=1 :
                time.sleep(5)
                check_focus = p.focus_status
                print("Alignemt thread! I am waiting for focusing finished!")
            if p.cancel_process==1:
                return
            fname1 = p.get_file_name(os.path.join(p.pos_path, "dicfocuscycle00"), ".tif")  # reference image
            p.fname1 = sort_by(fname1)
            fname2 = p.get_file_name(os.path.join(p.pos_path, "dicfocus" + p.cycle), ".tif")
            p.fname2 = sort_by(fname2)

            if len(fname2) != len(fname1):
                p.alignment_status = 0
                txt = get_time() + "current cycle's image number in dicfouce folder is not consistent with pre cycle!"
                update_error(txt)
                p.write_log(txt)
                return
            else:
                p.pos_batch_size = [i * scope_constant.pos_per_slice for i in p.slicePerSlide]

                imref = []
                imcurr = []

                for i in p.fname1:
                    im = cv2.imread(os.path.join(p.pos_path, "dicfocuscycle00", i), cv2.IMREAD_UNCHANGED)
                    imref.append(im)
                for j in p.fname2:
                    im = cv2.imread(os.path.join(p.pos_path, "dicfocus" + p.cycle, j), cv2.IMREAD_UNCHANGED)
                    imcurr.append(im)
                p.imref = np.array(imref)
                p.imcurr = np.array(imcurr)
                p.slidenum = np.zeros(sum(p.pos_batch_size))
                p.slidenum[0:p.pos_batch_size[0]] = 1
                print(p.pos_batch_size)
                for i in range(1, len(p.pos_batch_size)):
                    p.slidenum[sum(p.pos_batch_size[0:i]):sum(p.pos_batch_size[0:i + 1])] = int(i + 1)
                p.slidenum=p.slidenum.astype(int)
                print(p.slidenum)
                if len(p.slidenum) != len(p.imcurr):
                    p.alignment_status = 0
                    txt = get_time() + p.cycle + " The number of images is different from slice numbers. Abort.\n"
                    update_error(txt)
                    p.write_log(txt)

                else:
                    self.calculate_shift()

    def calculate_shift_singlethread(self, i):
        """Compute the XY translation offset for a single position index using phase correlation.

        Args:
            i: Index into self.imref and self.imcurr arrays.
        """
        p = self._parent
        add_highlight_from_scope("Image System start to alignment at " + str(i) + "th position\n")
        ref = p.imref[i]  # reference
        img = p.imcurr[i]
        xoffset, yoffset = self.imregcorr(img, ref)
        p.x_offset[i] = xoffset
        p.y_offset[i] = yoffset
        txt = get_time() + p.cycle + " finished " + str(i) + "th position\n"
        add_highlight_from_scope(txt)
        p.write_log(txt)

    def calculate_shift(self):
        """Run threaded phase-correlation alignment for all positions, then perform sanity checks.

        Spawns one thread per position to compute XY offsets, waits for all to complete,
        then calls sanity_check_alignment and update_regoffsetfile.
        """
        p = self._parent
        threads = []
        add_highlight_from_scope(get_time() + "Image System start to alignment!\n")
        p.x_offset = np.zeros(sum(p.pos_batch_size))
        p.y_offset = np.zeros(sum(p.pos_batch_size))
        p.i=100/sum(p.pos_batch_size)
        update_process_bar(0)
        update_process_label("Aligning")
        # if self.fine_align==0
        #     align_list=[]

        for i in range(sum(p.pos_batch_size)):
            if p.cancel_process ==1:
                txt=get_time()+"process canceled!"
                print(txt)
                p.write_log(txt)
                add_highlight_from_scope(txt)
                break
            update_process_bar(p.i)
            t = threading.Thread(target=self.calculate_shift_singlethread, args=(i,))
            t.start()
            threads.append(t)
            time.sleep(3)
            p.i = p.i + 100 / sum(p.pos_batch_size)
        for t in threads:
            t.join()
        update_process_bar(0)
        self.sanity_check_alignment()
        self.update_regoffsetfile()
        return

    def update_regoffsetfile(self):
        """Apply pooled alignment offsets to position CSV and JSON files.

        Reads the offset CSV, applies the pooled XY translation (converted to stage
        coordinates via pixel size and stage direction), and writes updated
        'regoffset' CSV and .pos JSON files for the microscope.
        """
        p = self._parent
        df = pd.read_csv(os.path.join(p.pos_path, 'offset' + p.cycle + '.csv'))
        df['x_adjust'] = df['x'] + p.stage_x_dir * p.x_translation_pooled * p.pixelsize
        df['y_adjust'] = df['y'] + p.stage_y_dir * p.y_translation_pooled * p.pixelsize
        df.to_csv(os.path.join(p.pos_path, 'regoffset' + p.cycle + '.csv'), index=False)
        filename = 'offset' + p.cycle + ".pos"
        new_filename = 'regoffset' + p.cycle + '.pos'
        with open(os.path.join(p.pos_path, filename)) as f:
            d = json.load(f)
        d2 = copy.deepcopy(d)
        if p.piezo==1:
            for i in df.index:
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][2]['Position_um']['array'][0] = df.loc[
                    i, 'x_adjust']
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][2]['Position_um']['array'][1] = df.loc[
                    i, 'y_adjust']
        else:
            for i in df.index:
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][1]['Position_um']['array'][0] = df.loc[
                    i, 'x_adjust']
                d2['map']['StagePositions']['array'][i]['DevicePositions']['array'][1]['Position_um']['array'][1] = df.loc[
                    i, 'y_adjust']
        json_object = json.dumps(d2, indent=2)
        with open(os.path.join(p.pos_path, new_filename), "w") as outfile:
            outfile.write(json_object)
        with open(os.path.join(p.pos_path, "pre_adjusted_pos.pos"), "w") as outfile:
            outfile.write(json_object)
        txt = get_time() + p.cycle + " saved regoffset.pos for microscope review and next cycle\n"
        add_highlight_from_scope(txt)
        p.write_log(txt)
        print("saved regoffset.pos for microscope review and next cycle")
        return

    def createBlackmanWindow(self, windowSize):
        """Create a 2D Blackman-Harris window for spectral leakage reduction in FFT-based registration.

        Generates a separable 2D window from the product of two 1D Blackman-Harris windows
        using the exact three-term coefficients (a0=7938/18608, a1=9240/18608, a2=1430/18608).

        Args:
            windowSize: Tuple of (M, N) specifying the window dimensions.

        Returns:
            2D NumPy array of shape (M, N) containing the window values.
        """
        M = windowSize[0]
        N = windowSize[1]
        a0 = 7938 / 18608;
        a1 = 9240 / 18608;
        a2 = 1430 / 18608;
        n = np.arange(1, N + 1, 1)
        m = np.arange(1, M + 1, 1)
        h1 = 1;
        h2 = 1;
        h1_part1 = a1 * np.cos(2 * math.pi * m / (M - 1))
        h1_part2 = a2 * np.cos(4 * math.pi * m / (M - 1))
        h2_part1 = a1 * np.cos(2 * math.pi * n / (N - 1))
        h2_part2 = a2 * np.cos(4 * math.pi * n / (N - 1))
        if M > 1:
            h1 = a0 - h1_part1 + h1_part2;
        if N > 1:
            h2 = a0 - h2_part1 + h2_part2;
        h1 = h1.reshape(len(h1), 1)
        h = np.multiply(h1, h2)
        return h

    def machineEpsilon(self, func=float):
        """Compute the machine epsilon for a given numeric type by iterative halving.

        Machine epsilon is the smallest value such that 1.0 + epsilon != 1.0.

        Args:
            func: Numeric type constructor (default: float).

        Returns:
            The machine epsilon value for the given type.
        """
        machine_epsilon = func(1)
        while func(1) + func(machine_epsilon) != func(1):
            machine_epsilon_last = machine_epsilon
            machine_epsilon = func(machine_epsilon) / func(2)
        return machine_epsilon_last

    def imregcorr(self, moving, fixed):
        """Compute sub-pixel XY translation between two images using phase correlation.

        Algorithm steps:
        1. Apply a Blackman-Harris window to both images to reduce edge artifacts.
        2. Compute the normalized cross-power spectrum via FFT.
        3. Find the peak in the inverse FFT (phase correlation surface).
        4. Refine the peak location to sub-pixel accuracy by fitting a 2D quadratic
           surface to the 3x3 neighborhood around the integer peak.

        Args:
            moving: 2D image array to be registered (current cycle).
            fixed: 2D reference image array (cycle00).

        Returns:
            Tuple of (x_offset, y_offset) in pixels, or None if process was cancelled.
        """
        p = self._parent
        if p.cancel_process == 1:
            return
        # Step 1: Convert to float and apply Blackman-Harris window to reduce
        # spectral leakage from image edges (non-periodic boundaries)
        moving = moving.astype('single')
        fixed = fixed.astype('single')
        windowSize = moving.shape
        h = self.createBlackmanWindow(windowSize)
        moving_1 = moving * h
        fixed_1 = fixed * h

        # Round pixel values to 3 decimal places to reduce floating-point noise
        A = fixed_1
        A_l = A.tolist()
        A = np.array([round(a, 3) for row in A_l for a in row]).reshape((2048, 2048))
        B = moving_1;
        B_l = B.tolist()
        B = np.array([round(b, 3) for row in B_l for b in row]).reshape((2048, 2048))

        # Step 2: Compute normalized cross-power spectrum
        # Zero-pad to (size_A + size_B - 1) for linear (non-circular) correlation
        size_A = np.array(A.shape)
        size_B = np.array(B.shape)
        outSize = size_A + size_B - 1;
        A_trans = np.fft.fft2(A, outSize)
        B_trans = np.fft.fft2(B, outSize)
        ABConj = A_trans * np.conj(B_trans);  # Cross-power spectrum

        eps = self.machineEpsilon(float)

        # Normalize by magnitude to get phase-only correlation
        denominator = abs(eps + ABConj)
        d = np.fft.ifft2(ABConj / denominator)

        # Step 3: Find integer peak location in the correlation surface
        d_shift = np.fft.fftshift(d)  # Shift zero-frequency to center
        d_shift_flatten = d_shift.flatten()
        result = np.where(d_shift_flatten == np.amax(d_shift_flatten))
        peak = np.unravel_index(result, d_shift.shape)
        ypeak = peak[0][0][0]
        xpeak = peak[1][0][0]

        # Step 4: Sub-pixel refinement via 2D quadratic surface fit
        # Extract 3x3 neighborhood around the integer peak
        u = np.real(d_shift[ypeak - 1:ypeak + 2, xpeak - 1:xpeak + 2])
        u = u.T.flatten()
        # Build design matrix for quadratic: f(x,y) = a0 + a1*x + a2*y + a3*xy + a4*x^2 + a5*y^2
        x = np.array([-1, -1, -1, 0, 0, 0, 1, 1, 1])
        y = np.array([-1, 0, 1, -1, 0, 1, -1, 0, 1])
        X = np.empty((6, 9))
        X[0] = np.ones(9)
        X[1] = x
        X[2] = y
        X[3] = x * y
        X[4] = x ** 2
        X[5] = y ** 2
        # Solve for coefficients via least-squares
        A1 = np.real(np.linalg.lstsq(X.T, u.T, rcond=None)[0])
        # Compute sub-pixel offset as the extremum of the fitted quadratic
        x_offset = (-A1[2] * A1[3] + 2 * A1[5] * A1[1]) / (A1[3] ** 2 - 4 * A1[4] * A1[5])
        y_offset = -1 / (A1[3] ** 2 - 4 * A1[4] * A1[5]) * (A1[3] * A1[1] - 2 * A1[4] * A1[2])
        # Round to 0.1 pixel precision
        x_offset = round(10 * x_offset) / 10;
        y_offset = round(10 * y_offset) / 10;
        xpeak = xpeak + 1 + x_offset;
        ypeak = ypeak + 1 + y_offset;
        peakVal = np.dot(np.array([1, x_offset, y_offset, x_offset * y_offset, x_offset ** 2, y_offset ** 2]), A1.T);
        peakVal = float(abs(peakVal))
        # Convert from correlation surface coordinates to actual displacement
        gridYCenter = round(1 + (d.shape[0] - 1) / 2)
        gridXCenter = round(1 + (d.shape[1] - 1) / 2)
        xpeak_1 = xpeak - gridXCenter;
        ypeak_1 = ypeak - gridYCenter;
        # If correlation is uniform (no clear peak), report zero offset
        if all((d == peakVal).flatten()):
            xpeak_1 = 0
            ypeak_1 = 0
        return xpeak_1, ypeak_1

    def sanity_check_alignment(self):
        """Pool alignment offsets per slide (median) and check for excessive tilt or registration failures.

        Computes per-slide median offsets and logs warnings if extreme differences
        (>50 pixels) are detected between positions on the same slide.
        """
        p = self._parent
        p.x_translation_pooled = np.zeros(len(p.slidenum))
        p.y_translation_pooled = np.zeros(len(p.slidenum))
        uniqslidenum = np.unique(p.slidenum);
        for i in uniqslidenum:
            x_median = np.median(p.x_offset[np.where(p.slidenum == i)])
            y_median = np.median(p.y_offset[np.where(p.slidenum == i)])
            p.x_translation_pooled[np.where(p.slidenum == i)] = x_median
            p.y_translation_pooled[np.where(p.slidenum == i)] = y_median
        p.alignment_status = 1
        for i in uniqslidenum:
            x_sub = p.x_offset[np.where(p.slidenum == i)]
            y_sub = p.y_offset[np.where(p.slidenum == i)]
            max_range_xy = max(np.ptp(x_sub, axis=0), np.ptp(y_sub, axis=0))
            x_extreme_diff = np.median(x_sub[0:scope_constant.pos_per_slice]) - np.median(
                x_sub[-scope_constant.pos_per_slice:])
            y_extreme_diff = np.median(y_sub[0:scope_constant.pos_per_slice]) - np.median(
                y_sub[-scope_constant.pos_per_slice:])
            if x_extreme_diff > 50:
                txt = get_time() + p.cycle + " Slide " + str(i) + ' is tilted COUNTER CLOCKWISE.\n'
                update_error(txt)
                p.write_log(txt)
                #p.alignment_status = 0
            if x_extreme_diff < -50:
                txt = get_time() + p.cycle + " Slide " + str(i) + ' is tilted CLOCKWISE.\n'
                update_error(txt)
                p.write_log(txt)
                #p.alignment_status = 0
            if max_range_xy > 50:
                txt = get_time() + p.cycle + " Slide " + str(
                    i) + ' is tilted CLOCKWISEgrossly tilted and/or some registrations have failed. Double-check fixed positions.\n'
                update_error(txt)
                p.write_log(txt)
                #p.alignment_status = 0
            print(p.cycle+" alignmentthread finish!")
        return
