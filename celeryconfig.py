from celery.schedules import crontab

imports = ('app.tasks', 'app.main.tasks', 'app.booker.tasks', 'app.notify.tasks', 'app.routing.tasks')
broker_url = 'amqp://'
accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = 'Canada/Mountain'
task_time_limit = 3000
worker_concurrency = 5

beat_schedule = {
    'backup_mongo': {
        'task': 'app.main.tasks.backup_mongo',
        'schedule': crontab(hour=1, minute=0, day_of_week='*')
    },
    'wipe_sessions': {
        'task': 'app.main.tasks.wipe_sessions',
        'schedule': crontab(hour=0, minute=5, day_of_week='*')
    },
     'update_maps': {
        'task': 'app.booker.tasks.update_maps',
        'schedule': crontab(hour=4, minute=0, day_of_week='*')
     },
     'find_inactive_donors': {
        'task': 'app.main.tasks.find_inactive_donors',
        'schedule': crontab(hour=5, minute=0, day_of_week='*')
     },
	'build_routes': {
		  'task': 'app.routing.tasks.build_scheduled_routes',
		  'schedule': crontab(hour=6, minute=30, day_of_week='*')
	 },
    'schedule_reminders': {
        'task': 'app.notify.tasks.schedule_reminders',
        'schedule': crontab(hour=7, minute=0, day_of_week='*')
    },
    'health_check': {
        'task': 'app.main.tasks.health_check',
        'schedule': crontab(hour='*', minute=10, day_of_week='*')
    },
	'monitor_triggers': {
		'task': 'app.notify.tasks.monitor_triggers',
    	'schedule': crontab(minute='*/10')
	},
    'update_calendar_blocks': {
        'task': 'app.main.tasks.update_calendar_blocks',
        'schedule': crontab(hour='6,9,13,15,18,21', minute=0, day_of_week='*')
     }
}
