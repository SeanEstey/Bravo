
#-------------------------------------------------------------------------------
def gauth(oauth):
    scope = [
       ['https://www.googleapis.com/auth/calendar.readonly']
    ]
    version = 'v3'
    name = 'calendar'

    try:
        credentials = SignedJwtAssertionCredentials(
            oauth['client_email'],
            oauth['private_key'],
            scope
        )

        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build(name, version, http=http)
    except Exception as e:
        logger.error('Error authorizing %s: %s', name, str(e))
        return False

    logger.debug('Drive service authorized')

    return service


#-------------------------------------------------------------------------------
def get_events(service, cal_id, start, end, oauth):
    '''Get a list of Google Calendar events between given dates.
    @oauth: dict oauth keys for google service account authentication
    @start, @end: naive datetime objects
    Returns: list of Event items on success, False on error
    Full-day events have datetime.date objects for start date
    Event object definition: https://developers.google.com/google-apps/calendar/v3/reference/events#resource
    '''

    start = start.replace(tzinfo=None)
    end = end.replace(tzinfo=None)

    try:
        events_result = service.events().list(
            calendarId = cal_id,
            timeMin = start.isoformat() +'-07:00', # MST ofset
            timeMax = end.isoformat() +'-07:00', # MST offset
            singleEvents = True,
            orderBy = 'startTime'
        ).execute()
    except Exception as e:
        logger.error('Error pulling cal events: %s', str(e))
        logger.error(start.isoformat())
        return False

    events = events_result.get('items', [])

    return events
