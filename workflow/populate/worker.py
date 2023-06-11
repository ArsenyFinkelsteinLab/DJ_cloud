import datajoint as dj
from datajoint_utilities.dj_worker import DataJointWorker, WorkerLog, ErrorLog

from workflow import db_prefix
from workflow.pipeline import analysis_pop
from workflow.pipeline import analysis_meso_svd
from workflow.pipeline import analysis_meso_svd_part
from workflow.pipeline import analysis_pop_area
from workflow.pipeline import meso_svd_autocorr
from workflow.pipeline import meso_svd_area_autocorr
from workflow.pipeline import meso_LDS
from workflow.pipeline import meso_svd_part
from workflow.pipeline import meso_svd_area2
from workflow.pipeline import meso_area_shuffle
from workflow.pipeline import area_svd_LDS
from workflow.pipeline import meso_comm_subspace
from workflow.pipeline import meso_comm_subspace4
from workflow.pipeline import meso_comm_subspace5
from workflow.pipeline import meso_comm_subspace_removed
from workflow.pipeline import meso_comm_subspace_basis
from workflow.pipeline import meso_comm_SVD

# from workflow.pipeline import analysis_new   # import another schema in the future

logger = dj.logger

__all__ = ['standard_worker', 'WorkerLog', 'ErrorLog']


# -------- Define process(s) --------
worker_schema_name = db_prefix + "workerlog"
autoclear_error_patterns = []

# standard process for non-GPU jobs
standard_worker = DataJointWorker('standard_worker',
                                  worker_schema_name,
                                  db_prefix=[db_prefix],
                                  run_duration=1,
                                  sleep_duration=20,
                                  autoclear_error_patterns=autoclear_error_patterns)

# restrict to 1 session
#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724'}
#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724', 'session': 2}
#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724', 'session': 1, 'session_epoch_number': 2}
#standard_worker(analysis_pop.ROISVDPython, max_calls=100)


##### Communication Subspace
# standard_worker(meso_comm_SVD.CommSubspaceSVD)



#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724', 'session': 7}
#standard_worker(analysis_pop.ROISVDPython)


###### Latest runs of SVD
#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724', 'time_bin': '0'}

#analysis_pop.ROISVDPython.key_source &= {'subject_id': '464725'}
#standard_worker(analysis_pop.ROISVDPython)


###### MESO SVD
#analysis_meso_svd.ROISVDPython.key_source &= {'subject_id': '464724'}
#standard_worker(analysis_meso_svd.ROISVD)

###### MESO LDS
# meso_LDS.SVDLDS.key_source &= {'observed_dim': '80', 'latent_dim': '60'}
# standard_worker(meso_LDS.SVDLDS)

###### Area LDS
# area_svd_LDS.AreaSVDLDS.key_source &= {'observed_dim': '80', 'latent_dim': '60'}
# standard_worker(area_svd_LDS.AreaSVDLDS)

###### MESO SVD Partition
#standard_worker(meso_svd_part.ROISVDPartition1)

###### MESO SVD Autocorr
#analysis_meso_svd.SVDTemporalComponentsAutocorr3.key_source &= {'subject_id': '463189'}
#standard_worker(meso_svd_autocorr.SVDTemporalComponentsAutocorr3)

###### Per-area SVD
#analysis_pop_area.ROISVDArea.key_source &= {'subject_id': '464725'}
#standard_worker(analysis_pop_area.ROISVDArea)

standard_worker(meso_svd_area2.ROISVDArea2)

###### Area SVD shuffled
#meso_area_shuffle.SVDAreaShuffle.key_source &= {'subject_id': '464724', 'session': '1'}
#standard_worker(meso_area_shuffle.SVDAreaShuffle)


###### Per-area SVD Autocorr
#analysis_pop_area.ROISVDArea.key_source &= {'subject_id': '464725'}
#standard_worker(meso_svd_area_autocorr.SVDAreaTemporalComponentsAutocorr)


#### Shared variance computation
#shared_variance_analysis.SVC.key_source &= {'subject_id': '464724', 'time_bin': '0'}
#standard_worker(shared_variance_analysis.SVC)


# example to add new workers  

# arseny_worker = DataJointWorker('arseny_worker',
#                                   worker_schema_name,
#                                   db_prefix=[db_prefix],
#                                   run_duration=1,
#                                   sleep_duration=20,
#                                   autoclear_error_patterns=autoclear_error_patterns)

# arseny_worker(analysis_new.FutureNewAnalysisTable, max_calls=20)
# arseny_worker(analysis_new.TableAnalysis, max_calls=20)
