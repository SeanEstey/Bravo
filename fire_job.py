import tasks

job_id = '544984f99b93873e475b2e10'
#tasks.fire_bulk_call.delay(job_id)
tasks.fire_bulk_call(job_id)

#monitor_bulk_call('544984f99b93873e475b2e10')
