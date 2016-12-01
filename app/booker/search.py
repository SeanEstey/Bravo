'''app.booker.search'''

from datetime import datetime, date, timedelta
import logging

from .. import etap, parser, gcal
from .. import db
from . import geo
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def search(agency, query):
    '''Search query invoked from Booker client
    @query: either Account Number, Postal Code, Address, or Block

    Returns: JSON object: {'search_type': str, 'status': str, 'description': str, 'results': array }
    '''

    conf = db.agencies.find_one({'name':agency})

    maps = db.maps.find_one({'agency':conf['name']})['features']

    events = []
    end_date = datetime.today() + timedelta(days=30)

    service = gcal.gauth(conf['google']['oauth'])

    for cal_id in conf['cal_ids']:
        events +=  gcal.get_events(
            service,
            conf['cal_ids'][cal_id],
            datetime.today(),
            end_date
        )

    if parser.is_account_id(query):
        try:
            account = etap.call(
              'get_account',
              conf['etapestry'],
              data={'account_number': query}
            )
        except Exception as e:
            logger.error('no account id %s', query)
            return False

        geo_results = geo.geocode(
            account['address'] + ', ' + account['city'] + ', AB',
            conf['google']['geocode']['api_key']
        )

        results = geo.get_nearby_blocks(
            coords,
            radius,
            maps,
            events
        )

        return {
            'search_type': 'account',
            'account': account,
            'results': results
        }
    elif parser.is_block(query):
        return {
            'search_type': 'block',
            'results': search_by_block(
                query,
                events,
                conf['booker']
            ),
            'description': \
                'Booking suggestions for Block <b>' + query + '</b> '\
                'within next <b>sixteen weeks</b>'
        }

    elif parser.is_postal_code(query):
        return {
            'search_type': 'postal',
            'results': search_by_postal(
                query,
                events,
                maps,
                conf['booker'],
                conf['google']['geocode']['api_key']
            ),
            'description': \
                'Booking suggestions for Postal Code <b>' +\
                query.substring(0,3) + '</b> within next <b>ten weeks</b>'

        }
    # must be address?
    else:
        geo_results = geo.geocode(
            query,
            conf['google']['geocode']['api_key']
        )

        if len(geo_results) == 0:
            return {
                'status': 'failed',
                'description': \
                    'Could not find local address. '\
                    'Make sure to include quadrant (i.e. NW) and Postal Code.'
            }

        results = geo.get_nearby_blocks(
            geo_results[0]['geometry']['location'],
            4.0,
            maps,
            events
        )

        return {
            'status': 'success',
            'search_type': 'address',
            'results': results,
            'description': \
                'Booking suggestions for Address <b>' +\
                query + '</b> within next <b>ten weeks</b>'
        }

#-------------------------------------------------------------------------------
def make(account_num, udf, type, config):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @type: 'delivery, pickup'
    '''

    '''
    logger.info('Making ' + type + ' booking for account ' + account_num + ', udf: ' + udf)

    response = Server.call('make_booking', {'account_num':account_num, 'udf':udf, 'type':type}, config['etapestry'])

    logger.info(response.getContentText())

    return response.getContentText()
    '''
    return True

#-------------------------------------------------------------------------------
def search_by_radius(coords, radius, maps, events):
    '''Find a list of Blocks within the smallest radius of given coordinates.
    Constraints: must be within provided radius, schedule date, and block size.

    @coords: {'lat':float, 'lng':float}
    @rules: specifies schedule, radius and block size constraints
    Returns: list of Block objects on success, [] on failure
    '''

    found = false

    # Start with small radius, continually expand radius until match found
    while found == False:
        if radius > rules['max_block_radius']:
            break

        results = geo.get_nearby_blocks(coords, radius, maps, events)

        if len(bookings) > 0:
            found = true
        else:
          logger.info('No match found within ' + radius.toString() + ' km. Expanding search.')

          radius += 1.0

    #if found:
    #    for i in range(len(booking)):
    #        if is_res(bookings[i].block)):
    #            bookings[i]['max_size'] = rules['size']['res']['max']
    #        else:
    #            bookings[i]['max_size'] = rules['size']['bus']['max']

    # May be empty array
    return bookings


#-------------------------------------------------------------------------------
def search_by_block(block, events, conf):
    '''Find all the scheduled dates/info for the given block.
    @rules: Object specifying search parameters: 'search_weeks' and
    'size':'res':'max' and 'size:'bus':'max'
    Returns: list of Block objects on success, [] on failure
    '''

    '''
    today = new Date()
    end_date = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * rules['search_weeks']))
    res_events = Schedule.getEventsBetween(cal_ids['res'], today, end_date)
    bus_events = Schedule.getEventsBetween(cal_ids['bus'], today, end_date)
    events = res_events.concat(bus_events)
    '''

    results = []

    for event in events:
        cal_block = parser.get_block(event['summary'])

        if block != cal_block:
            continue

        '''
        result = {
          'block': block_name,
          'date': parseDate(events[i].start.date),
          'location': events[i].location,
          'event_name': events[i].summary.substring(0, events[i].summary.indexOf(']')+1),
          'booking_size':Parser.getBookingSize(events[i].summary)
        }

        if(is_res(block_name))
          result['max_size'] = rules['size']['res']['max']
        else
          result['max_size'] = rules['size']['bus']['max']
        '''

        results.push(result)

    sorted(
        results,
        key=lambda event: event['start'].get('dateTime', event['start'].get('date'))
    )

    return results

#-------------------------------------------------------------------------------
def search_by_postal(postal, events, maps, conf, api_key, account=None):
    '''Finds all Blocks within given postal code, sorted, sorted by date.
    Returns: list of Block objects on success, [] on failure.
    '''

    '''
    postal = postal.toUpperCase()
    today = new Date()
    ten_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 10))
    res_events = Schedule.getEventsBetween(cal_ids['res'], today, ten_weeks)
    bus_events = Schedule.getEventsBetween(cal_ids['bus'], today, ten_weeks)
    events = res_events.concat(bus_events)

    results = []
    for(i=0 i < events.length i++) {
    event = events[i]

    if(!event.location) {
      logger.info('Calendar event ' + event.summary + ' missing postal code')
      continue
    }

    postal_codes = event.location.split(",")

    for(n=0 n<postal_codes.length n++) {
      if(postal_codes[n].trim() != postal.substring(0,3))
        continue

      block = get_block(event.summary)
      result = {
        'block': block,
        'date': parseDate(event.start.date),
        'event_name': event.summary.substring(0, event.summary.indexOf(']')+1),
        'location': event.location,
        'booking_size':Parser.getBookingSize(event.summary)
      }

      if(is_res(block))
        result['max_size'] = rules['size']['res']['max']
      else
        result['max_size'] = rules['size']['bus']['max']

      results.push(result)
    }
    }

    results.sort(function(a, b) {
    return a.date.getTime() - b.date.getTime()
    })

    return results
    }
    '''
    return True
