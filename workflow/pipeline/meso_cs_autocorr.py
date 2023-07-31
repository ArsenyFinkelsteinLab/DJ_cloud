"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
from math import *
import scipy
import math

schema = dj.Schema('lee_meso_analysis')

exp2 = dj.VirtualModule('exp2', 'arseny_s1alm_experiment2')
img = dj.VirtualModule('img', 'arseny_learning_imaging')
meso = dj.VirtualModule('meso', 'lee_meso_analysis')
lab = dj.VirtualModule('lab', 'map_lab')
stimanal = dj.VirtualModule('stimanal', 'arseny_learning_photostim_anal')


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


@schema
class CSTemporalComponentsAutocorr(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> meso.SourceBrainArea
    -> meso.TargetBrainArea
    component_id         : int                          
    threshold            : double                       # threshold for defining the autocorrelation timescale
    time_bin             : double                       # time window used for binning the data. 0 means no binning
    ---
    temporal_component_autocorr: blob           # the auto correlation of the temporal component of the CS
    temporal_component_autocorr_tau: blob       # the time constant of the auto correlation, a vector of taus for each component """

    @property
    def key_source(self):
        return (exp2.SessionEpoch*meso.SourceBrainArea*meso.TargetBrainArea & img.ROIdeltaF & img.ROIBrainArea & stimanal.MiceIncluded) - exp2.SessionEpochSomatotopy

    def make(self, key):

        time_bin = 0
        threshold_vector = [1, 2]
        lags = 50

        key['time_bin'] = time_bin
        # rel_souce_area = meso.SourceBrainArea
        # rel_target_area = meso.TargetBrainArea
        # brain_area_strings = rel_souce_area.fetch('source_brain_area')

        target_brain_area = key['target_brain_area']
        source_brain_area = key['source_brain_area']

        if target_brain_area == source_brain_area:
            return

        rel_FOVEpoch = img.FOVEpoch & key
        rel_FOV = img.FOV & key
        if 'imaging_frame_rate' in rel_FOVEpoch.heading.secondary_attributes:
            imaging_frame_rate = rel_FOVEpoch.fetch1('imaging_frame_rate')
        else:
            imaging_frame_rate = rel_FOV.fetch1('imaging_frame_rate')
     

        rel_basis = meso.CommSubspaceBasis & key
        CS_basis = rel_basis.fetch1('basis')

        rel_data_area = (img.ROIdeltaF*img.ROIBrainArea) - img.ROIBad
        rel_data_tot = (img.ROIdeltaF & key) - img.ROIBad

        
        source_key = key
        source_key.pop('source_brain_area')
        source_key.pop('target_brain_area')
        source_key['brain_area'] = source_brain_area
        F_source = FetchChunked(rel_data_area & source_key, rel_data_tot & source_key, 'roi_number', 'dff_trace', 500)
        F_source_binned = np.array([MakeBins(Fi.flatten(), time_bin * imaging_frame_rate) for Fi in F_source])
        F_source_binned = F_source_binned[:500,:]

        key.pop('brain_area')
        key['target_brain_area'] = target_brain_area
        key['source_brain_area'] = source_brain_area

        source_temporal_components = np.dot(CS_basis.T, F_source_binned)

        # for area in brain_area_strings:
        for threshold in threshold_vector:

            
            # key['threshold'] = threshold

            num_comp = source_temporal_components.shape[0]

            tau = np.empty((num_comp,1))
            acorr_all = np.empty((num_comp,lags))
            for i in range(num_comp):

                data = source_temporal_components[i]
                mean = np.mean(data)
                var = np.var(data)
                ndata = data - mean
                acorr = np.correlate(ndata, ndata, 'full')[len(ndata)-1:] 
                acorr = acorr[range(lags)] / var / len(ndata)
            #  acorr = sm.tsa.acf(data, nlags = lags-1)
                time_bin_scaling = time_bin
                if time_bin == 0:
                    time_bin_scaling = 1
                ts = np.argmax(acorr < np.exp(-threshold)) / imaging_frame_rate * time_bin_scaling
                if ts == 0:
                    ts = lags
                tau[i] = ts
                acorr_all[i] = acorr

            key_meso = {**key, 'time_bin': time_bin, 'threshold': threshold}    
            key_comps = [{**key_meso, 'component_id': ic, 'temporal_component_autocorr_tau': tau[ic], 'temporal_component_autocorr': acorr_all[ic]}
                            for ic in range(num_comp)]
            self.insert(key_comps, allow_direct_insert=True)