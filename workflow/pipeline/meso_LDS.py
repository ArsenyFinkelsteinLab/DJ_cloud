"""This module was auto-generated by datajoint from an existing schema"""

import datajoint as dj
import numpy as np
from bisect import bisect
from math import *

import autograd.numpy as np
import autograd.numpy.random as npr

import ssm

schema = dj.Schema('lee_meso_analysis')

exp2 = dj.VirtualModule('exp2', 'arseny_s1alm_experiment2')
img = dj.VirtualModule('img', 'arseny_learning_imaging')
meso = dj.VirtualModule('meso', 'lee_meso_analysis')


@schema
class SVDLDS(dj.Computed):
    definition = """
    -> exp2.SessionEpoch
    observed_dim         : int                          # number of observed PC dimensions
    latent_dim           : int                          # dimension of inferred LDS
    ---
    lds_matrix           : double                       # matrix of inferred LDS
    elbos                : blob                         # evidence lower bound  """

    @property
    def key_source(self):
        return (exp2.SessionEpoch & meso.SVDTemporalComponents)

    def make(self, key):

        session_epoch_type = key['session_epoch_type']
        if session_epoch_type == 'spont_only':
            observed_dim_vals = [40]
            latent_dim_vals = [20]
        else:
            observed_dim_vals = [40]
            latent_dim_vals = [20]

        for observed_dim in observed_dim_vals:
            for latent_dim in latent_dim_vals:
                
                rel_comp = meso.SVDTemporalComponents & 'component_id<%d' % observed_dim
                rel = rel_comp & key & 'time_bin = 0' & 'threshold_for_event = 0'
                temporal_components = rel.fetch('temporal_component', order_by='component_id')
                data = np.vstack(temporal_components).T

                lds = ssm.LDS(observed_dim, latent_dim, emissions="gaussian")
                elbos, q = lds.fit(data, method="laplace_em", num_iters=30)

                A_est = lds.dynamics.A
                
                key_LDS = {**key, 'observed_dim': observed_dim, 'latent_dim': latent_dim}    
                self.insert1({**key_LDS, 'lds_matrix': A_est, 'elbos': elbos}, allow_direct_insert=True)
