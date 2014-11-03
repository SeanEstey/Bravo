import sys
sys.path.insert(0, '/root/bravo')

#import tasks
import bravo

job_id = '544984f99b93873e475b2e10'
#tasks.monitor_job(job_id)
#bravo.create_job_summary(job_id)
bravo.send_email_report(job_id)

