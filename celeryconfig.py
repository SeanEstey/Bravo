from celery.schedules import crontab

imports = ('app.tasks',)
broker_url = 'amqp://'
accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = 'Canada/Mountain'
task_time_limit = 3000
worker_concurrency = 1

# WARNING: causes IOErrors reconnecting to eventlet if used
#worker_max_tasks_per_child = 10

beat_schedule = {
    'mem_check': {
        'task': 'app.main.tasks.mem_check',
        'schedule': crontab(hour='*', minute=0, day_of_week='*')
    },
    'schedule_reminders': {
        'task': 'app.notify.tasks.schedule_reminders',
        'schedule': crontab(hour=7, minute=0, day_of_week='*')
        #'schedule': crontab(minute='*/5'),
        #'kwargs': {'agcy':'vec'}
    },
	'monitor_triggers': {
		'task': 'app.notify.tasks.monitor_triggers',
    	'schedule': crontab(minute='*/10')
        #'schedule': crontab(minute='*/1')
	},
	'build_routes': {
		  'task': 'app.routing.tasks.build_scheduled_routes',
		  'schedule': crontab(hour=6, minute=30, day_of_week='*')
          #'schedule': crontab(minute='*/5'),
          #'kwargs': {'agcy':'vec'}
	 },
     'update_calendar_blocks': {
        'task': 'app.main.tasks.update_calendar_blocks',
        'schedule': crontab(hour='6,9,12,15,18,21', minute=0, day_of_week='*')
     },
     'find_inactive_donors': {
        'task': 'app.main.tasks.find_inactive_donors',
        'schedule': crontab(hour=5, minute=0, day_of_week='*')
        #'schedule': crontab(minute='*/5'),
        #'kwargs': {'agcy':'vec'}
     }
}
