"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
import scipy
from scipy import sparse
import math
from math import *

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

    CXX = np.dot(X.T,X) + sigma * np.identity(np.size(X,1))
    CXY = np.dot(X.T,Y)
    B_OLS = np.dot(np.linalg.pinv(CXX), CXY)
    
    Y_OLS = np.dot(X,B_OLS)
    _U, _S, V = np.linalg.svd(Y_OLS, full_matrices=False)
    
    B = B_OLS
    Vr = 0
    if rank > 0:
        V = V.T
        Vr = V[:,:rank]
        B = np.dot(B, np.dot(Vr,Vr.T))

    err = Y - np.dot(X,B)
    err = err.flatten()
    mse = np.mean(np.power(err,2))
    Y = Y.flatten()
    ss = np.mean(np.power(Y,2))

    return mse, ss, B, Vr



@schema
class CommSubspaceSVD(dj.Computed):
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
        return (exp2.SessionEpoch*meso.SourceBrainArea*meso.TargetBrainArea & img.ROIdeltaF & img.ROIBrainArea & stimanal.MiceIncluded & meso.SVDAreaTemporalComponents) - exp2.SessionEpochSomatotopy
    
    def make(self, key):
    	# So far the code is only correct for threshold == 0
        threshold_for_event = 0 # [0, 1, 2]

        ncomps = 40
        max_comp = 200
        r2_all = np.empty((ncomps, 2))
        r2_all[:] = np.nan

        time_bin_vector = [0]

        sigma = 1

        rel_FOVEpoch = img.FOVEpoch & key
        rel_FOV = img.FOV & key
        rel_data_area = (img.ROIdeltaF*img.ROIBrainArea) - img.ROIBad
        rel_data_tot = (img.ROIdeltaF & key) - img.ROIBad
        rel_SVD = meso.SVDAreaTemporalComponents & 'time_bin = 0' & 'component_id < %d'% max_comp & 'threshold_for_event = 0'

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
        source_key['brain_area'] = source_brain_area
        rel_SVD = rel_SVD & source_key
        temporal_components = rel_SVD.fetch('temporal_component', order_by='component_id')
        temporal_components = np.vstack(temporal_components)
        target_key = source_key
        target_key['brain_area'] = target_brain_area
        F_target = FetchChunked(rel_data_area & target_key, rel_data_tot & target_key, 'roi_number', 'dff_trace', 500)


        for time_bin in time_bin_vector:

            flag = 0
            insert_key = key
            insert_key.pop('brain_area')
            insert_key['source_brain_area'] = source_brain_area                    
            insert_key['target_brain_area'] = target_brain_area
            
            F_target_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_target])
            # nneurons = 500
            # nneurons2 = F_target_binned.shape[0]
            # nneurons = min(nneurons,nneurons2)
            
            if nneurons < 500:
                flag = 1
            else: 
                ntimepoints = temporal_components.shape[1]
                if ntimepoints < 1500:
                    flag = 1
     
            # nneurons = 500
            ntimepoints = 1500
            F_target_binned = F_target_binned[:nneurons,:ntimepoints]
            temporal_components = temporal_components[:,:ntimepoints]

            if flag:
                insert_key2 = {**insert_key, 'time_bin': time_bin, 'threshold_for_event': threshold_for_event}
                self.insert1({**insert_key2, 'r2': r2_all}, allow_direct_insert=True)
                return

            # if len(temporal_components) == 0:
            #     flag = 1

            comp_vals = (np.floor(np.linspace(1, max_comp, ncomps, endpoint=True))).astype(int)

            for i in range(ncomps):
                comps = comp_vals[i]
                reduced_tc = temporal_components[:comps,:]
                mse, ss, B, V = reduced_reg(reduced_tc.T,F_target_binned.T,0,sigma)
                r2_all[i,0] = 1 - mse / ss

            r2_all[:,1] = comp_vals.T

            insert_key2 = {**insert_key, 'time_bin': time_bin, 'threshold_for_event': threshold_for_event}
            self.insert1({**insert_key2, 'r2': r2_all}, allow_direct_insert=True)

