import datajoint as dj
from datajoint_utilities.dj_worker import DataJointWorker, WorkerLog, ErrorLog

from workflow import db_prefix
from workflow.pipeline import analysis_pop
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
analysis_pop.ROISVDPython.key_source &= {'subject_id': '464724', 'session': 2, 'session_epoch_number': 2}


#standard_worker(analysis_pop.ROISVDPython)

standard_worker(analysis_pop.ROISVDPython, max_calls=100)

# example to add new workers  

# arseny_worker = DataJointWorker('arseny_worker',
#                                   worker_schema_name,
#                                   db_prefix=[db_prefix],
#                                   run_duration=1,
#                                   sleep_duration=20,
#                                   autoclear_error_patterns=autoclear_error_patterns)

# arseny_worker(analysis_new.FutureNewAnalysisTable, max_calls=20)
# arseny_worker(analysis_new.TableAnalysis, max_calls=20)

# 
