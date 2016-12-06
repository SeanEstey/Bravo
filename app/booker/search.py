'''app.booker.search'''

from datetime import datetime, date, timedelta
import logging

from .. import etap, parser, gcal
from .. import db
from . import geo
logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def search(agency, query):
    '''Search query invoked from Booker client
    @query: either Account Number, Postal Code, Address, or Block

    Returns: JSON object: {'search_type': str, 'status': str, 'description': str, 'results': array }
    '''

    conf = db.agencies.find_one({'name':agency})

    maps = db.maps.find_one({'agency':conf['name']})['features']

    events = []
    end_date = datetime.today() + timedelta(days=100)

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
            geo_results[0]['geometry']['location'],
            4.0,
            maps,
            events
        )

        return {
            'status': 'success',
            'query_type': 'account',
            'account': account,
            'results': results,
            'description': \
                'Booking suggestions for <b>' + account['name'] + '</b> '\
                'within next <b>ten weeks</b>'
        }
    elif parser.is_block(query):
        return {
            'status': 'success',
            'query_type': 'block',
            'results': search_by_block(query, events),
            'description': \
                'Booking suggestions for Block <b>' + query + '</b> '\
                'within next <b>sixteen weeks</b>'
        }

    elif parser.is_postal_code(query):
        return {
            'status': 'success',
            'query_type': 'postal',
            'results': search_by_postal(query, events),
            'description': \
                'Booking suggestions for Postal Code <b>' +\
                query[0:3] + '</b> within next <b>ten weeks</b>'
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
            'query_type': 'address',
            'results': results,
            'description': \
                'Booking suggestions for Address <b>' +\
                query + '</b> within next <b>ten weeks</b>'
        }

#-------------------------------------------------------------------------------
def book(agency, aid, block, date_str, driver_notes):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @aid: eTap account id
    '''

    logger.info('Booking account %s for %s', aid, date_str)

    conf = db.agencies.find_one({'name':agency})

    try:
        response = etap.call(
          'make_booking',
          conf['etapestry'],
          data={
            'account_num': int(aid),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***' + driver_notes + '***',
                'Office Notes': '***RMV ' + block + '***',
                'Block': block,
                'Next Pickup Date': date_str
            }
          }
        )
    except EtapError as e:
        return {
            'status': 'failed',
            'description': 'etapestry error: %s' % str(e)
        }
    except Exception as e:
        logger.error('failed to book: %s', str(e))
        return {
            'status': 'failed',
            'description': str(e)
        }

    return {
        'status': 'success',
        'description': response
    }

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
def search_by_block(block, events):
    '''Find all the scheduled dates/info for the given block.
    @rules: Object specifying search parameters: 'search_weeks' and
    'size':'res':'max' and 'size:'bus':'max'
    Returns: list of Block objects on success, [] on failure
    '''

    results = []

    for event in events:
        cal_block = parser.get_block(event['summary'])

        if block != cal_block:
            continue

        '''
        if(is_res(block_name))
          result['max_size'] = rules['size']['res']['max']
        else
          result['max_size'] = rules['size']['bus']['max']
        '''

        results.append({
            'name': block,
            'event': event,
            'distance': '0.0km',
            'area': parser.get_area(event['summary']) or '---',
            'booked': parser.get_num_booked(event['summary']) or '---'
        })


    sorted(
        results,
        key=lambda k: k['event']['start'].get('dateTime',k['event']['start'].get('date'))
    )

    return results

#-------------------------------------------------------------------------------
def search_by_postal(postal, events):
    '''Finds all Blocks within given postal code, sorted, sorted by date.
    Returns: list of Block objects on success, [] on failure.
    '''

    postal = postal.upper()

    results = []

    for event in events:
        if not event.get('location'):
            logger.info('Calendar event ' + event['summary'] + ' missing postal code')
            continue

        postals = event['location'].split(",")

        for _postal in postals:
              if _postal.strip() != postal[0:3]:
                continue

              #if(is_res(block))
              #  result['max_size'] = rules['size']['res']['max']
              #else
              #  result['max_size'] = rules['size']['bus']['max']

              results.append({
                'name': parser.get_block(event['summary']),
                'event': event,
                # TODO: calculate distance
                'distance': '---',
                'area': parser.get_area(event['summary']) or '---',
                'booked': parser.get_num_booked(event['summary']) or '---'
              })

    #results.sort(function(a, b) {
    #return a.date.getTime() - b.date.getTime()
    #})

    return results
