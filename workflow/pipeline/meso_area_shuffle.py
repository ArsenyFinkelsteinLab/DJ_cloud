"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
import scipy
# import os.path
from bisect import bisect
import math
from math import *
import random

schema = dj.Schema('lee_meso_analysis')

exp2 = dj.VirtualModule('exp2', 'arseny_s1alm_experiment2')
img = dj.VirtualModule('img', 'arseny_learning_imaging')
lab = dj.VirtualModule('lab', 'map_lab')


def FetchChunked(relation_area, relation_tot, idx_name, val_name, chunk_size):
    idx = relation_tot.fetch(idx_name, order_by=idx_name)
    num_elements = len(idx)
    num_chunks = (num_elements + (chunk_size - 1)) // chunk_size
    parts = []
    for i_chunk in range(num_chunks):
        i = i_chunk * chunk_size + 1
        # Don't need to manually check for the remainder; relation does it
        rel_part = relation_area & f"{idx_name} >= {i}" & f"{idx_name} < {i + chunk_size}"
        parts.append(np.asarray(rel_part.fetch(val_name, order_by=idx_name)))
    return np.concatenate(parts)


def InsertChunked(relation, data, chunk_size):
    num_elements = len(data)
    num_chunks = (num_elements + chunk_size - 1) // chunk_size
    for i_chunk in range(num_chunks):
        i = i_chunk * chunk_size
        relation.insert(data[i : min(i + chunk_size, num_elements)])


def MakeBins(F, bin_size):
    ceiled_bin_size = math.ceil(bin_size)
    if ceiled_bin_size == 0:
        return F
    num_bins = len(F) // ceiled_bin_size
    return [sum(F[i * ceiled_bin_size : (i + 1) * ceiled_bin_size]) / ceiled_bin_size for i in range(num_bins)]


def NormalizeF(F_binned, threshold, flag_zscore):
    if threshold > 0:
        F_zscored = scipy.stats.zscore(F_binned, 1)
        for i, fzs in enumerate(F_zscored):
            if fzs <= threshold:
                F_binned[i] = 0
    if flag_zscore: # zscoring the data
        return scipy.stats.zscore(F_binned, 1)
    else: # only centering the data
        return [f - fm for f, fm in zip(F_binned, np.mean(F_binned, 1))]


def FloatRange(start, stop, step):
    num_steps = int((stop - start) / step) + 1
    return [start + i * step for i in range(num_steps)]


@schema
class SVDAreaShuffle(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> img.ROI
    -> lab.BrainArea
    realization          : double                       # index of random realization of ROI subset
    ---
    singular_values      : longblob                     # singular values of each SVD temporal component, ordered from larges to smallest value
    """

    @property
    def key_source(self):
        return (exp2.SessionEpoch*lab.BrainArea & img.ROIdeltaF & img.ROIBrainArea) - exp2.SessionEpochSomatotopy

    def make(self, key):
    	# So far the code is only correct for threshold == 0
        threshold_for_event = 0 # [0, 1, 2]

        time_bin = 0
        flag_zscore = 1
        num_ROIs = 500
        num_realizations = 100

        for realization in range(num_realizations):
            self.compute_SVD(key, flag_zscore, time_bin, threshold_for_event, realization, num_ROIs)

    def compute_SVD(self, key, flag_zscore, time_bin, threshold, realization, num_ROIs):
        rel_FOVEpoch = img.FOVEpoch & key
        rel_FOV = img.FOV & key
        rel_data_area = (img.ROIdeltaF*img.ROIBrainArea & key) - img.ROIBad
        rel_data_tot = (img.ROIdeltaF & key) - img.ROIBad

        if 'imaging_frame_rate' in rel_FOVEpoch.heading.secondary_attributes:
            imaging_frame_rate = rel_FOVEpoch.fetch1('imaging_frame_rate')
        else:
            imaging_frame_rate = rel_FOV.fetch1('imaging_frame_rate')

        # TODO: Use unique_roi_number or something esle to guarantee consistent order
        # (but unique_roi_number is not a primary key)

        if 'dff_trace' in rel_data_area.heading.secondary_attributes:
            F = FetchChunked(rel_data_area & key, rel_data_tot & key, 'roi_number', 'dff_trace', 500)
        else:
            F = FetchChunked(rel_data_area & key, rel_data_tot & key, 'roi_number', 'spikes_trace', 500)

        F_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F])
        N = F_binned.shape[0]
        if N < num_ROIs:
            return

        ROI_list = random.sample(range(1, N), num_ROIs)

        F_rand = F_binned[ROI_list,:]  
        F_normalized = NormalizeF(F_rand, threshold, flag_zscore)

        u, s, vh = np.linalg.svd(F_normalized, full_matrices=False)

        # Populating POP.SVDAreaSingularValues and POP.SVDAreaTemporalComponents
        svd_key = {**key, 'realization': realization}
        self.insert1({**svd_key, 'singular_values': s}, allow_direct_insert=True)
