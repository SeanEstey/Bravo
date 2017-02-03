from celery.schedules import crontab

imports = ('app.tasks',)
broker_url = 'amqp://'
accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = 'Canada/Mountain'
task_time_limit = 3000
worker_concurrency = 1
beat_schedule = {
	'monitor_triggers': {
		'task': 'app.notify.tasks.monitor_triggers',
		'schedule': crontab(minute='*/5')
	 },
	'build_routes': {
		  'task': 'app.routing.tasks.build_routes',
		  'schedule': crontab(hour=6, minute=30, day_of_week='*')
	 },
     'update_calendar_blocks': {
        'task': 'app.main.tasks.update_calendar_blocks',
        'schedule': crontab(hour='6,9,12,15,18,21', minute=0, day_of_week='*')
     }
}
