from parser import is_block, is_postal_code, is_account_id
from routing import geocode
import etap
from block_parser import get_block, is_res_block

from app import app, db, info_handler, error_handler, debug_handler, login_manager

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
def search(term, config, agency)
    '''Search query invoked from Booker client
    @term: either Account Number, Postal Code, Address, or Block
    Returns: JSON object: {'search_type': str, 'status': str, 'message': str, 'booking_results': array }
    '''

    results = {
    'search_term': term,
    'search_type': ''
    }

    if is_block(term):
        results['search_type'] = 'block'
    elif is_postal_code(term):
        results['search_type']  = 'postal'
    elif is_account_id(term):
        results['search_type']  = 'account'

    if results['search_type'] == 'block':
        results['booking_results'] = Booking.findBlockSchedule(
            term,
            config['cal_ids'],
            config['booking']
        )
        results['message'] = 'Booking suggestions for Block <b>' + term + '</b>'\
        ' within next <b>sixteen weeks</b>'

        break

    elif results['search_type'] == 'postal':
        results['booking_results'] = Booking.getOptionsByPostal(term,
                config['cal_ids'], config['booking'])
        results['message'] = 'Booking suggestions for Postal Code <b>' +
        term.substring(0,3) + '</b> within next <b>ten weeks</b>'
        break

    elif results['search_type'] == 'account':
        account_id = term

        if account_id[0] == '/':
            account_id = account_id[1:]

        logger.info('search by account #')

        try:
            account = etap.call(
              'get_account',
              etapestry_id,
              {'account_number': account_id}
            )
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)
            results['status'] = 'failed'
            results['message'] = 'Account <b>' + term + '</b> not found in eTapestry'
            break

        results['account_id'] = account['id']
        results['account_name'] = account['name']

        #var geo = Maps.newGeocoder().geocode(account['address'] + ',' + account['postalCode'])

        # TODO: get routific api_key
        api_key = ''
        result = geocode(account['address'], api_key)

        if result == False:
            results['status'] = 'failed'
            results['message'] = 'Could not find local address. '\
                    'Make sure to include quadrant (i.e. NW) and Postal Code'
            break

        if account['nameFormat'] == 3):  #BUSINESS
            results['booking_results'] = \
                Booking.getOptionsByPostal(
                    account['postalCode'],
                    config['cal_ids'],
                    config['booking'])

            results['message'] = \
                    'Booking suggestions for account <b>' + account['name'] \
                    + '</b> in <b>' + account['postalCode'].substring(0,3)\
                    + '</b> within next <b>14 days</b>'
        else:
            # TODO: map_data undefined. using agency name arg instead

            results['booking_results'] = \
                Booking.getOptionsByRadius(
                    geo.results[0].geometry.location.lat,
                    geo.results[0].geometry.location.lng,
                    map_data,
                    config['cal_ids'],
                    config['booking'])

            results['message'] = \
                'Booking suggestions for account <b>' + account['name'] \
                + '</b> in <b>10km</b> within next <b>14 days</b>'

        break

        # Likely an Address
        default:
            results['search_type'] = 'address'

            # TODO: retrieve routific api_key
            api_key = ''
            result = geocode(term, api_key)

            if result == False:
                results['status'] = 'failed'
                results['message'] = \
                  'Did you search for an address? Could not locate <b>'+term+'</b>.'\
                  ' Make sure to include quadrant (i.e. NW) and Postal Code'

                break

            results['message'] = \
              'Booking suggestions for <b>' + term + '</b> in <b>10km</b>'\
              ' within next <b>14 days</b>'

            results['booking_results'] = Booking.getOptionsByRadius(
                geo.results[0].geometry.location.lat,
                geo.results[0].geometry.location.lng,
                map_data,
                config['cal_ids'],
                config['booking']
            )

            break

    return JSON.stringify(results)


#-------------------------------------------------------------------------------
def make(account_num, udf, type, config):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @type: 'delivery, pickup'
    '''

    logger.info('Making ' + type + ' booking for account ' + account_num + ', udf: ' + udf)

    response = Server.call('make_booking', {'account_num':account_num, 'udf':udf, 'type':type}, config['etapestry'])

    logger.info(response.getContentText())

    return response.getContentText()


#-------------------------------------------------------------------------------
def get_options_by_radius(lat, lng, map_data, cal_ids, rules, _events):
    '''Find a list of Blocks within the smallest radius of given coordinates.
    Constraints: must be within provided radius, schedule date, and block size.
    @rules: specifies schedule, radius and block size constraints
    Returns: list of Block objects on success, [] on failure
    '''

    today = new Date()
    two_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * rules['max_schedule_days_wait']))
    radius = 4.0

    found = false

    bookings = []

    # Start with small radius, continually expand radius until match found
    while found == False:
        if radius > rules['max_block_radius']:
            break

        bookings = Geo.findBlocksWithin(lat, lng, map_data, radius, two_weeks, cal_ids['res'], _events)

        if len(bookings) > 0:
            found = true
        else:
          logger.info('No match found within ' + radius.toString() + ' km. Expanding search.')

          radius += 1.0

    if found:
        for i in range(len(booking)):
            if is_res_block(bookings[i].block)):
                bookings[i]['max_size'] = rules['size']['res']['max']
            else:
                bookings[i]['max_size'] = rules['size']['bus']['max']

    # May be empty array
    return bookings


#-------------------------------------------------------------------------------
def find_block_schedule(block_name, cal_ids, rules):
    '''Find all the scheduled dates/info for the given block.
    @rules: Object specifying search parameters: 'search_weeks' and
    'size':'res':'max' and 'size:'bus':'max'
    Returns: list of Block objects on success, [] on failure
    '''

    today = new Date()
    end_date = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * rules['search_weeks']))
    res_events = Schedule.getEventsBetween(cal_ids['res'], today, end_date)
    bus_events = Schedule.getEventsBetween(cal_ids['bus'], today, end_date)
    events = res_events.concat(bus_events)

    results = []
    for(i=0 i<events.length i++) {
    cal_block = get_block(events[i].summary)

    if(block_name != cal_block)
      continue

    result = {
      'block': block_name,
      'date': parseDate(events[i].start.date),
      'location': events[i].location,
      'event_name': events[i].summary.substring(0, events[i].summary.indexOf(']')+1),
      'booking_size':Parser.getBookingSize(events[i].summary)
    }

    if(is_res_block(block_name))
      result['max_size'] = rules['size']['res']['max']
    else
      result['max_size'] = rules['size']['bus']['max']

    results.push(result)
    }

    results.sort(function(a, b) {
    return a.date.getTime() - b.date.getTime()
    })

    return results
    }


#-------------------------------------------------------------------------------
def get_options_by_postal(postal, cal_ids, rules):
    '''Finds all Blocks within given postal code, sorted, sorted by date.
    Returns: list of Block objects on success, [] on failure.
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

      if(is_res_block(block))
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
