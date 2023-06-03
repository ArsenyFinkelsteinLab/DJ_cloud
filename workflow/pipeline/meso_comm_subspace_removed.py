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
class CommSubspaceRemoved(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> meso.SourceBrainArea
    -> meso.TargetBrainArea
    threshold_for_event  : double                       # threshold in deltaf_overf
    time_bin             : double                       # time window used for binning the data. 0 means no binning
    num_comps_removed    : int
    ---
    r2            : blob
    """

    @property
    def key_source(self):
        return (exp2.SessionEpoch*meso.SourceBrainArea*meso.TargetBrainArea & img.ROIdeltaF & img.ROIBrainArea & stimanal.MiceIncluded) - exp2.SessionEpochSomatotopy
    
    def make(self, key):

        target_brain_area = key['target_brain_area']
        source_brain_area = key['source_brain_area']

        if target_brain_area == source_brain_area:
            return
        
    	# So far the code is only correct for threshold == 0
        threshold_for_event = 0 # [0, 1, 2]

        nranks = 40
        comps = [0, 1, 2, 5, 10, 20, 50]
        ncomps = len(comps)
        rel_temp = img.Mesoscope & key
        time_bin_vector = [0]

        sigma = 1

        rel_FOVEpoch = img.FOVEpoch & key
        rel_FOV = img.FOV & key

        rel_data1 = meso.ROISVD & (img.ROIGood - img.ROIBad)
        rel_data2 = meso.SVDSingularValues  & (img.Mesoscope)
        rel_data3 = meso.SVDTemporalComponents  & img.Mesoscope

        rel_roi = img.ROI*img.ROIBrainArea & (img.ROIGood - img.ROIBad)
        key.pop('source_brain_area')
        key.pop('target_brain_area')
        source_key = key
        roi_list = (rel_roi & key).fetch('roi_number')
        roi_list = [x - 1 for x in roi_list]

        U = (rel_data1 & key).fetch('roi_components')
        U = np.vstack(U)
        S = (rel_data2 & key).fetch('singular_values')
        S = np.diag(S[0])
        V = (rel_data3 & key).fetch('temporal_component')
        V = np.vstack(V)


        if 'imaging_frame_rate' in rel_FOVEpoch.heading.secondary_attributes:
            imaging_frame_rate = rel_FOVEpoch.fetch1('imaging_frame_rate')
        else:
            imaging_frame_rate = rel_FOV.fetch1('imaging_frame_rate')

        source_key['brain_area'] = source_brain_area
        source_roi_list = (rel_roi & source_key).fetch('roi_number')
        source_roi_list = [x - 1 for x in source_roi_list]
        # F_source = FetchChunked(rel_data_area & source_key, rel_data_tot & source_key, 'roi_number', 'dff_trace', 500)
        target_key = source_key
        target_key['brain_area'] = target_brain_area
        target_roi_list = (rel_roi & target_key).fetch('roi_number')
        target_roi_list = [x - 1 for x in target_roi_list]
        # F_target = FetchChunked(rel_data_area & target_key, rel_data_tot & target_key, 'roi_number', 'dff_trace', 500)
        insert_key = key
        insert_key.pop('brain_area')
        insert_key['source_brain_area'] = source_brain_area                    
        insert_key['target_brain_area'] = target_brain_area
        num_components = 200

        for num_comp_2remove in comps:
            r2_all = np.empty((nranks, 2))
            r2_all[:] = np.nan

            Ur = U[:, num_comp_2remove:num_components]
            Vr = V[num_comp_2remove:num_components, :]
            Sr = S[num_comp_2remove:num_components, num_comp_2remove:num_components]

            F_reconstruct = np.dot(Ur, np.dot(Sr,Vr))

            
            F_new = np.empty((max(roi_list)+1, F_reconstruct.shape[1]))
            F_new[roi_list,:] = F_reconstruct
            F_reconstruct = F_new

            F_source = F_reconstruct[source_roi_list, :]
            F_target = F_reconstruct[target_roi_list, :]

            for time_bin in time_bin_vector:

                flag = 0
                
                F_source_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_source])
                F_target_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_target])
                nneurons = F_source_binned.shape[0]
                nneurons2 = F_target_binned.shape[0]
                nneurons = min(nneurons,nneurons2)
                
                if nneurons < 500:
                    flag = 1
                else: 
                    ntimepoints = F_source_binned.shape[1]
                    if ntimepoints < 1500:
                        flag = 1
                
                if flag:
                    insert_key2 = {**insert_key, 'time_bin': time_bin, 'threshold_for_event': threshold_for_event}
                    self.insert1({**insert_key2, 'r2': r2_all}, allow_direct_insert=True)
                    return
            
                
                nneurons = 500
                ntimepoints = 1500
                F_source_binned = F_source_binned[:nneurons,:ntimepoints]
                F_target_binned = F_target_binned[:nneurons,:ntimepoints]

                rank_vals = (np.floor(np.linspace(0, nneurons, nranks, endpoint=True))).astype(int)

                for i in range(nranks):
                    rank = rank_vals[i]
                    mse, ss, B, Vr = reduced_reg(F_source_binned.T,F_target_binned.T,rank,sigma)
                    r2_all[i,0] = 1 - mse / ss

                r2_all[:,1] = rank_vals.T

                insert_key2 = {**insert_key, 'time_bin': time_bin, 'threshold_for_event': threshold_for_event, 'num_comps_removed': num_comp_2remove}
                self.insert1({**insert_key2, 'r2': r2_all}, allow_direct_insert=True)
