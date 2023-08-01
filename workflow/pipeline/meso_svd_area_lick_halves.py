"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
import scipy
# import os.path
from bisect import bisect
import math
from math import *


dj.config['database.host'] = 'datajoint.mesoscale-activity-map.org'
dj.config['database.user'] = 'lee'
dj.config['database.password'] = 'verify'
conn = dj.conn()


schema = dj.Schema('lee_meso_analysis')

exp2 = dj.VirtualModule('exp2', 'arseny_s1alm_experiment2')
img = dj.VirtualModule('img', 'arseny_learning_imaging')
stimanal = dj.VirtualModule('stimanal', 'arseny_learning_photostim_anal')
lab = dj.VirtualModule('lab', 'map_lab')
tracking = dj.VirtualModule('tracking', 'arseny_learning_tracking')
meso = dj.VirtualModule('meso', 'lee_meso_analysis')

def FetchChunked(relation_area, relation_tot, idx_name, val_name, chunk_size):
    idx = relation_tot.fetch(idx_name, order_by=idx_name)
    num_elements = len(idx)
    num_chunks = (num_elements + (chunk_size - 1)) // chunk_size
    # num_chunks = min(num_chunks,2)
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



def get_trial_times_relative_to_lick(key, frame_rate, time_bin, flag_electric_video):

    TrialsStartFrame = ((img.FrameStartTrial & key) - tracking.VideoGroomingTrial).fetch('session_epoch_trial_start_frame', order_by='trial')
    trial_num = ((img.FrameStartTrial & key) - tracking.VideoGroomingTrial).fetch('trial', order_by='trial')

    if len(TrialsStartFrame) == 0:
        TrialsStartFrame = (img.FrameStartFile & key).fetch('session_epoch_file_start_frame', order_by='session_epoch_file_num')
        trial_num = ((exp2.BehaviorTrial & key) - tracking.VideoGroomingTrial).fetch('trial', order_by='trial')
        TrialsStartFrame = TrialsStartFrame[trial_num]

    if flag_electric_video == 1:
        LICK_VIDEO = []  # We align based on electric lickport, even if video does not exist
    elif flag_electric_video == 2:
        # We align based on video if it exists
        # We align to the first video-detected lick after lickport movement
        LICK_VIDEO = ((tracking.VideoNthLickTrial & key) - tracking.VideoGroomingTrial).fetch('lick_time_onset_relative_to_trial_start')

    go_time = (((exp2.BehaviorTrial.Event & key) - tracking.VideoGroomingTrial) & 'trial_event_type="go"').fetch('trial_event_time')
    LICK_ELECTRIC = ((exp2.ActionEvent & key) - tracking.VideoGroomingTrial).fetch()

    start_file = np.zeros(len(trial_num))
    end_file = np.zeros(len(trial_num))
    lick_file = np.zeros(len(trial_num))
   
    for i_tr in range(len(trial_num)):
        if len(LICK_VIDEO) > 0:
            all_licks = LICK_VIDEO[LICK_VIDEO['trial'] == trial_num[i_tr]]['lick_time_onset_relative_to_trial_start']
            licks_after_go = all_licks[all_licks > go_time[i_tr]]
        else:
            all_licks = LICK_ELECTRIC[LICK_ELECTRIC['trial'] == trial_num[i_tr]]['action_event_time']
            licks_after_go = all_licks[all_licks > go_time[i_tr]]
        
        if len(licks_after_go) > 0:
            start_file[i_tr] = TrialsStartFrame[i_tr] + int(float(licks_after_go[0]) * frame_rate) + int(time_bin[0] * frame_rate)
            end_file[i_tr] = start_file[i_tr] + int(float(time_bin[1] - time_bin[0]) * frame_rate) - 1
                        
            if start_file[i_tr] <= 0:
                start_file[i_tr] = float('nan')
                end_file[i_tr] = float('nan')

        else:
            start_file[i_tr] = float('nan')
            end_file[i_tr] = float('nan')

    return start_file, end_file


def get_partition_by_lick(F,imaging_frame_rate,key):

    start_bin = -6
    end_bin = 8
    start_file, end_file = get_trial_times_relative_to_lick(key, imaging_frame_rate, [start_bin, end_bin], 1)

    num_trials = len(start_file)

    F_before_lick = []
    F_after_lick = []

    for i_tr in range(num_trials):

        start_frame = start_file[i_tr]
        if isnan(start_frame):
            continue

        start_frame = int(start_frame)
        end_frame = int(end_file[i_tr])
        lick_frame = start_frame + int((end_frame - start_frame)/2)

        tmp_before = F[:, start_frame : lick_frame]
        tmp_after = F[:, lick_frame+1 : end_frame]

        F_before_lick.append(tmp_before)
        F_after_lick.append(tmp_after)

    return np.concatenate(F_before_lick,axis=1), np.concatenate(F_after_lick,axis=1)



@schema
class ROISVDAreaLickHalves(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> img.ROI
    -> lab.BrainArea
    threshold_for_event  : double                       # threshold in zscore, after binning. 0 means we don't threshold. 1 means we take only positive events exceeding 1 std, 2 means 2 std etc.
    time_bin             : double                       # time window used for binning the data. 0 means no binning
    before_lick_flag     : int                          # 0 if before lick, 1 if after
    ---
    roi_components       : longblob                     # contribution of the temporal components to the activity of each neurons; fetching this table for all neurons should give U in SVD of size (neurons x components) for the top num_comp components
    """

    @property
    def key_source(self): 
        return (exp2.SessionEpoch*lab.BrainArea & img.ROIdeltaF & img.ROIBrainArea & stimanal.MiceIncluded & 'session_epoch_type = "behav_only"') - exp2.SessionEpochSomatotopy

    def make(self, key):
    	# So far the code is only correct for threshold == 0
        thresholds_for_event = [0] # [0, 1, 2]

        rel_temp = img.Mesoscope & key
        time_bin_vector = [0]

        flag_zscore = 1
        threshold_variance_explained = 0.9
        num_components_save = 500

        self2 = SVDAreaSingularValuesLick
        for i, time_bin in enumerate(time_bin_vector):
            self.compute_SVD(self2, key, flag_zscore, time_bin, thresholds_for_event, threshold_variance_explained, num_components_save)

    def compute_SVD(self, self2, key, flag_zscore, time_bin, thresholds_for_event, threshold_variance_explained, num_components_save):
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

        # nneurons = F_binned.shape[0]        
        # if nneurons < 200:
          # return
        
        nneurons = 1
        
        # F_binned = F_binned[:nneurons, :]
        num_pieces = 2
        F_partitioned = get_partition_by_lick(F_binned,imaging_frame_rate,key,num_pieces)
  
        for j in range(num_pieces):

            F_part = F_partitioned[j]

            for threshold in thresholds_for_event:
                F_normalized = NormalizeF(F_part, threshold, flag_zscore)

                u, s, vh = np.linalg.svd(F_normalized, full_matrices=False)

                # in numpy, s is already just a vector; no need to take diag
                squared_s = s ** 2
                num_components_save = min(num_components_save, nneurons)
                variance_explained = squared_s / sum(squared_s) # a feature of SVD. proportion of variance explained by each component
                cumulative_variance_explained = np.cumsum(variance_explained)
                num_comp = bisect(cumulative_variance_explained, threshold_variance_explained)
                u_limited = [ui[:num_comp] for ui in u]
                vt = vh[:num_components_save]

                key_ROIs = (rel_data_area & key).fetch('KEY', order_by='roi_number')
                key_ROIs = key_ROIs[:nneurons]
                for i in range(nneurons):
                    key_ROIs[i]['roi_components'] = u[i,:]
                    key_ROIs[i]['time_bin'] = time_bin
                    key_ROIs[i]['threshold_for_event'] = threshold
                    key_ROIs[i]['before_lick_flag'] = j

                InsertChunked(self, key_ROIs, 1000)

                svd_key = {**key, 'time_bin': time_bin, 'threshold_for_event': threshold, 'before_lick_flag': j}
                self2.insert1({**svd_key, 'singular_values': s}, allow_direct_insert=True)


@schema
class SVDAreaSingularValuesLickHalves(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    -> lab.BrainArea
    threshold_for_event  : double                       # threshold in deltaf_overf
    time_bin             : double                       # time window used for binning the data. 0 means no binning
    before_lick_flag     : int                          # 0 if before lick, 1 if after
    ---
    singular_values      : longblob                     # singular values of each SVD temporal component, ordered from larges to smallest value
    """
