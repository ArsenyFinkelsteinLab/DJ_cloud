"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
import scipy
from scipy import sparse
import math
from math import *
import os

schema = dj.Schema('lee_meso_analysis')

exp2 = dj.VirtualModule('exp2', 'arseny_s1alm_experiment2')
img = dj.VirtualModule('img', 'arseny_learning_imaging')
stimanal = dj.VirtualModule('stimanal', 'arseny_learning_photostim_anal')
lab = dj.VirtualModule('lab', 'map_lab')
meso = dj.VirtualModule('meso', 'lee_meso_analysis')


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


def reduced_reg(X,Y,rank,sigma):
    mX = np.mean(X, axis = 1, keepdims=True)
    mY = np.mean(Y, axis = 1, keepdims=True)
    X = X - mX
    Y = Y - mY

    CXX = np.dot(X.T,X) + sigma * sparse.eye(np.size(X,1))
    CXY = np.dot(X.T,Y)
    B_OLS = np.dot(np.linalg.inv(CXX), CXY)
    
    Y_OLS = np.dot(X,B_OLS)
    _U, _S, V = np.linalg.svd(Y_OLS, full_matrices=False)
    
    B = B_OLS
    Vr = 0
    if rank > 0:
        Vr = V[:,:rank]
        B = np.dot(B, np.dot(Vr,Vr.T))

    err = Y - np.dot(X,B)
    err = err.flatten()
    mse = np.mean(np.power(err,2))
    Y = Y.flatten()
    ss = np.mean(np.power(Y,2))

    return mse, ss, B, Vr




@schema
class CommSubspace4(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> meso.SourceBrainArea
    -> meso.TargetBrainArea
    threshold_for_event  : double                       # threshold in deltaf_overf
    time_bin             : double                       # time window used for binning the data. 0 means no binning
    ---
    r2            : blob
    """

    @property
    def key_source(self):
        return (exp2.SessionEpoch*meso.SourceBrainArea*meso.TargetBrainArea & 'session_epoch_type = "spont_only"' & img.ROIdeltaF & img.ROIBrainArea & stimanal.MiceIncluded) - exp2.SessionEpochSomatotopy

    def make(self, key):
    	# So far the code is only correct for threshold == 0
        threshold_for_event = 0 # [0, 1, 2]

        max_lag = 5
        nranks = 5
        r2_all = np.empty((nranks, max_lag))

        rel_temp = img.Mesoscope & key
        time_bin_vector = [0]

        flag_zscore = 1
        sigma = 1

        rel_FOVEpoch = img.FOVEpoch & key
        rel_FOV = img.FOV & key
        rel_data_area = (img.ROIdeltaF*img.ROIBrainArea) - img.ROIBad
        rel_data_tot = (img.ROIdeltaF & key) - img.ROIBad

        if 'imaging_frame_rate' in rel_FOVEpoch.heading.secondary_attributes:
            imaging_frame_rate = rel_FOVEpoch.fetch1('imaging_frame_rate')
        else:
            imaging_frame_rate = rel_FOV.fetch1('imaging_frame_rate')

        target_brain_area = key['target_brain_area']
        source_brain_area = key['source_brain_area']

        if target_brain_area == source_brain_area:
            return
        
        source_key = key
        source_key.pop('source_brain_area')
        source_key.pop('target_brain_area')
        target_key = source_key
        source_key['brain_area'] = source_brain_area
        target_key['brain_area'] = target_brain_area


        F_source = FetchChunked(rel_data_area & source_key, rel_data_tot & source_key, 'roi_number', 'dff_trace', 500)
        F_target = FetchChunked(rel_data_area & target_key, rel_data_tot & target_key, 'roi_number', 'dff_trace', 500)


        for time_bin in time_bin_vector:

            F_source_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_source])
            nneurons = F_source_binned.shape[0]
            ntimepoints = F_source_binned.shape[1]
            nneurons = min(nneurons,2000)

            if nneurons == 0:
                return


            F_target_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_target])
            nneurons2 = F_target_binned.shape[0]
            nneurons = min(nneurons,nneurons2)

            F_source_binned = F_source_binned[:nneurons,:]
            F_target_binned = F_target_binned[:nneurons,:]

            rank_vals = (np.floor(np.linspace(0, nneurons, nranks, endpoint=True))).astype(int)

            rank_vals = (np.floor(np.linspace(0, nneurons, nranks, endpoint=True))).astype(int)
            insert_key = key
            insert_key.pop('brain_area')
            insert_key['source_brain_area'] = source_brain_area                    
            insert_key['target_brain_area'] = target_brain_area

            for i in range(nranks):
                for j in range(max_lag):
                    rank = rank_vals[i]
                    lag = j
                    if lag > 0:
                        F_s_lagged = F_source_binned[:, lag:]
                        F_t_lagged = F_target_binned[:, :-lag]
                    else:
                        F_s_lagged = F_source_binned
                        F_t_lagged = F_target_binned
                    mse, ss, B, V = reduced_reg(F_s_lagged.T,F_t_lagged.T,rank,sigma)
                    r2_all[i,j] = 1 - mse / ss

                    
            insert_key2 = {**insert_key, 'time_bin': time_bin, 'threshold_for_event': threshold_for_event}
            self.insert1({**insert_key2, 'r2': r2_all}, allow_direct_insert=True)


            
