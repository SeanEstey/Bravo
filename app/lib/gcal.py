'''app.lib.gcal'''
import logging
from datetime import datetime
from .utils import dump_bson
log = logging.getLogger(__name__)

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
def gauth(keyfile_dict):

    from .gservice_acct import auth
    return auth(
        keyfile_dict,
        name='calendar',
        scopes=['https://www.googleapis.com/auth/calendar'],
        version='v3')

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
        log.exception('Error pulling cal events: %s', e.message)
        raise

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
        log.exception("Error updating Calendar Event",
            extra={'name':rv['summary'], 'date':rv['start']['date']})
        raise

    log.debug('Updated event %s...', rv['summary'][0:4],
        extra={'event':dump_bson(dump_event(rv))})

#-------------------------------------------------------------------------------
def get_colors(srvc):
    '''
    '''
    colors = srvc.colors().get().execute()

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

#-------------------------------------------------------------------------------
def dump_event(item):
    return {
        'title': item['summary'],
        'description': item.get('description'),
        'location': item.get('location'),
        'start': item['start'],
        'end': item['end']
    }
