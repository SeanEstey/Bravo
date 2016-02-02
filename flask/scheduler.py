from app import celery_app, db, logger, login_manager

@celery_app.task
def get_next_pickups(job_id):
  try:
    job_id = ObjectId(job_id)
    messages = db['msgs'].find({'job_id':job_id}, {'imported.block':1})
    blocks = []
    for msg in messages:
      if msg['imported']['block'] not in blocks:
        blocks.append(msg['imported']['block'])

    # Generated on google developer console
    f = file("google_api_key.p12", "rb")
    key = f.read()
    f.close()

    credentials = SignedJwtAssertionCredentials(
      service_account_name = GOOGLE_SERVICE_ACCOUNT,
      private_key = key,
      scope = 'https://www.googleapis.com/auth/calendar.readonly'
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    start_search = datetime.now() + timedelta(days=30)
    end_search = start_search + timedelta(days=70)

    service = build('calendar', 'v3', http=http)
    events = service.events().list(
      calendarId = ETW_RES_CALENDAR_ID,
      timeMin = start_search.isoformat()+'+01:00',
      timeMax = end_search.isoformat()+'+01:00',
      singleEvents = True,
      orderBy = 'startTime'
      #maxResults = 50
    ).execute()

    logger.info('%i calendar events pulled', len(events['items']))

    pickup_dates = {}
    for block in blocks:
      # Search calendar events to find pickup date
      for event in events['items']:
        cal_block = event['summary'].split(' ')[0]
        if cal_block == block:
          logger.debug('Block %s Pickup Date: %s', block, event['start']['date'])
          dt = dateutil.parser.parse(event['start']['date'])
          pickup_dates[block] = dt
      if block not in pickup_dates:
        logger.info('No pickup found for Block %s', block)

    #logger.info('pickup_date list' + json.dumps(pickup_dates))

    # Now we should have pickup dates for all blocks on job
    # Iterate through each msg and store pickup_date
    for block, date in pickup_dates.iteritems():
      logger.debug('Updating all %s with Next Pickup: %s', block, date)
      db['msgs'].update(
        {'job_id':job_id, 'imported.block':block}, 
        {'$set':{'next_pickup':date}},
        multi=True
      )
  
  except Exception, e:
    logger.error('get_next_pickups', exc_info=True)
    return str(e)

