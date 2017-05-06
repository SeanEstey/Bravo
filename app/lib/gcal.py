'''app.lib.gcal'''
import httplib2, json, logging, requests
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.discovery import build
from .utils import print_vars
from logging import getLogger
log = getLogger(__name__)

color_ids = {
    'light_purple' : 1,
    'aqua' : 2,
    'purple' : 3,
    'light_red' : 4,
    'yellow' : 5,
    'orange' : 6,
    'turqoise' : 7,
    'gray' : 8,
    'blue' : 9,
    'green' : 10,
    'red' : 11}

#-------------------------------------------------------------------------------
def gauth(oauth):

    try:
        scopes=['https://www.googleapis.com/auth/calendar']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            oauth,
            scopes=scopes)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('calendar', 'v3', http=http, cache_discovery=False)
    except Exception as e:
        log.error('Error authorizing gcal: %s', str(e))
        return False

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
        log.error('Error pulling cal events: %s', str(e))
        return False

    events = events_result.get('items', [])

    return events

#-------------------------------------------------------------------------------
def update_event(srvc, item, title=None, location=None, desc=None, color_id=None):
    '''events.update pydoc: https://tinyurl.com/hllg2cu
    '''

    try:
        rv = srvc.events().update(
            calendarId= item['organizer']['email'],
            eventId= item['id'],
            body= {
                'summary': title or item.get('summary'),
                'start': item['start'],
                'end': item['end'],
                'location': location or item.get('location'),
                'description': desc or item.get('description'),
                'colorId': color_id or item.get('colorId')
            }
        ).execute()
    except Exception as e:
        log.error('error updating event. desc=%s', str(e))
        log.debug(str(e))
        raise

    log.debug('updated event="%s", date="%s"', rv['summary'], rv['start']['date'])

#-------------------------------------------------------------------------------
def get_colors(srvc):
    '''
    '''
    colors = srvc.colors().get().execute()
    log.debug(print_vars(colors))

    # Print available calendarListEntry colors.
    for id, color in colors['calendar'].iteritem():
        print 'colorId: %s' % id
        print '  Background: %s' % color['background']
        print '  Foreground: %s' % color['foreground']
    # Print available event colors.
    for id, color in colors['event'].iteritem():
        print 'colorId: %s' % id
        print '  Background: %s' % color['background']
        print '  Foreground: %s' % color['foreground']

#-------------------------------------------------------------------------------
def evnt_date_to_dt(date_):
    parts = date_.split('-')
    return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
