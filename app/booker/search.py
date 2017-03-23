'''app.booker.search'''
from datetime import datetime, timedelta
import logging, re
from flask import g
from app import get_logger, get_keys
from app.main import parser
from app.main.etap import call, EtapError
from app.lib import gcal
from . import geo
log = get_logger('booker.search')

#-------------------------------------------------------------------------------
def search(query, radius=None, weeks=None, agcy=None):
    '''Search query invoked from Booker client
    @query: either Account Number, Postal Code, Address, or Block
    Returns JSON object: {'search_type': str, 'status': str, 'description': str,
    'results': array }
    '''

    agcy = agcy if agcy else g.user.agency

    maps = g.db.maps.find_one({'agency':agcy})['features']

    SEARCH_WEEKS = int(weeks or 12)
    SEARCH_DAYS = int(SEARCH_WEEKS * 7)
    SEARCH_RADIUS = float(radius or 4.0)

    events = []
    start_date = datetime.today()# + timedelta(days=1)
    end_date = datetime.today() + timedelta(days=SEARCH_DAYS)

    service = gcal.gauth(get_keys('google',agcy=agcy)['oauth'])
    cal_ids = get_keys('cal_ids',agcy=agcy)

    for id_ in cal_ids:
        events +=  gcal.get_events(
            service,
            cal_ids[id_],
            start_date,
            end_date)

    events =sorted(
        events,
        key=lambda k: k['start'].get('dateTime',k['start'].get('date')))

    if parser.is_account_id(query):
        try:
            acct = call(
              'get_acct',
              get_keys('etapestry',agcy=agcy),
              data={'acct_id': re.search(r'\d{1,6}',query).group(0)})
        except EtapError as e:
            log.error('no account id %s', query)

            return {
                'status': 'failed',
                'description': 'No account found matching ID <b>%s</b>.'% query}

        if not acct.get('address') or not acct.get('city'):
            return {
                'status': 'failed',
                'description': \
                    'Account <b>%s</b> is missing address or city. '\
                    'Check the account in etapestry.'% acct['name']}

        geo_results = geo.geocode(
            acct['address'] + ', ' + acct['city'] + ', AB',
            get_keys('google',agcy=agcy)['geocode']['api_key'])

        # Individual account (Residential donor)
        if acct['nameFormat'] <= 2:
            results = geo.get_nearby_blocks(
                geo_results[0]['geometry']['location'],
                SEARCH_RADIUS,
                maps,
                events)
            desc = \
                'Found <b>%s</b> options for account <b>%s</b> within '\
                '<b><a id="a_radius" href="#">%skm</a> radius</b> '\
                'in next <b>%s weeks.</b>'%(
                len(results), acct['name'], SEARCH_RADIUS, SEARCH_WEEKS)
        # Business account
        elif acct['nameFormat'] == 3:
            postal = acct['postalCode'][0:3]
            results = search_by_postal(postal, events)
            desc = \
                'Found <b>%s</b> options for account <b>%s</b> '\
                'within postal code <b>%s</b> in next <b>%s weeks.</b>'%(
                len(results), acct['name'], postal, SEARCH_WEEKS)

        return {
            'status': 'success',
            'query': query,
            'query_type': 'account',
            'radius': SEARCH_RADIUS,
            'weeks': SEARCH_WEEKS,
            'account': acct,
            'results': results,
            'description': desc
        }
    elif parser.is_block(query):
        results = search_by_block(query,events)
        return {
            'status': 'success',
            'query': query,
            'query_type': 'block',
            'weeks': SEARCH_WEEKS,
            'results': results,
            'description': \
                'Found <b>%s</b> results for <b>%s</b> in next <b>%s weeks</b>.'%(
                len(results), query, SEARCH_WEEKS)
        }

    elif parser.is_postal_code(query):
        results = search_by_postal(query, events)
        return {
            'status': 'success',
            'query': query,
            'query_type': 'postal',
            'weeks': SEARCH_WEEKS,
            'results': results,
            'description': \
                'Found <b>%s</b> results for Postal Code <b>%s</b> in next <b>%s weeks.</b>'%(
                len(results), query[0:3], SEARCH_WEEKS)
        }
    # must be address?
    else:
        geo_results = geo.geocode(
            query,
            get_keys('google',agcy=agcy)['geocode']['api_key']
        )

        if len(geo_results) == 0:
            return {
                'status': 'failed',
                'description': \
                    'No results found for address <b>%s</b>. '\
                    'Make sure to include quadrant (i.e. NW) and City.'%(
                    query)
            }

        results = geo.get_nearby_blocks(
            geo_results[0]['geometry']['location'],
            SEARCH_RADIUS,
            maps,
            events
        )

        return {
            'status': 'success',
            'query': query,
            'radius': SEARCH_RADIUS,
            'weeks': SEARCH_WEEKS,
            'query_type': 'address',
            'results': results,
            'description': \
                'Found <b>%s</b> options for address <b>%s</b> within '\
                '<b><a id="a_radius" href="#">%skm</a> radius</b> '\
                'in next <b>%s weeks.</b>'%(
                len(results), query, SEARCH_RADIUS, SEARCH_WEEKS)
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
          log.info('No match found within ' + radius.toString() + ' km. Expanding search.')

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
            'booked': parser.route_size(event['summary']) or '---'
        })


    results = sorted(
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
            log.info('Calendar event ' + event['summary'] + ' missing postal code')
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
                'booked': parser.route_size(event['summary']) or '---'
              })

    results = sorted(
        results,
        key=lambda k: k['event']['start'].get('dateTime',k['event']['start'].get('date'))
    )

    return results
