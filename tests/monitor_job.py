import sys
sys.path.insert(0, '/root/bravo')

import tasks

job_id = '544984f99b93873e475b2e10'
tasks.monitor_job(job_id)
#monitor.send_email_report(job_id)

