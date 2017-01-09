'''app.gcal'''

import logging
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
import requests
import json

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def gauth(oauth):
    try:
        credentials = SignedJwtAssertionCredentials(
            oauth['client_email'],
            oauth['private_key'],
            ['https://www.googleapis.com/auth/calendar.readonly']
        )

        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('calendar', 'v3', http=http)
    except Exception as e:
        logger.error('Error authorizing gcal: %s', str(e))
        return False

    logger.debug('calendar service authorized')

    return service

#-------------------------------------------------------------------------------
def get_events(service, cal_id, start, end):
    '''Get a list of Google Calendar events between given dates.
    @start, @end: naive datetime objects
    Full-day events have datetime.date objects for start date
    Event object definition: https://developers.google.com/google-apps/calendar/v3/reference/events#resource
    '''

    try:
        events_result = service.events().list(
            calendarId = cal_id,
            timeMin = start.replace(tzinfo=None).isoformat() +'-07:00', # MST ofset
            timeMax = end.replace(tzinfo=None).isoformat() +'-07:00', # MST offset
            singleEvents = True,
            orderBy = 'startTime'
        ).execute()
    except Exception as e:
        logger.error('Error pulling cal events: %s', str(e))
        return False

    events = events_result.get('items', [])

    return events
