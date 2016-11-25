import logging
import matplotlib.path as mplPath
import numpy as np

from app import db
from app.routing import geo

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def find_block(address):
    r = geo.geocode(address)

    coords = [
      r['geometry']['location']['lat'],
      r['geometry']['location']['lng']]

    map_name = find_map(coords)

    if map_name:
        return map_name[0:map_name.find(' [')]

    return False

#-------------------------------------------------------------------------------
def find_map(point):
    maps = db['maps'].find_one({})['features']

    for map_ in maps:
        coords = map_['geometry']['coordinates'][0]

        twod = []
        for c in coords:
            twod.append([c[1],c[0]])

        bbPath = mplPath.Path(np.array(twod))

        if bbPath.contains_point(point):
            print map_['properties']['name']
            return map_['properties']['name']

    print 'Map not found'
    return False


#-------------------------------------------------------------------------------
def find_blocks_within(lat, lng, map_data, radius, end_date, cal_id, _events):
    '''Return list of scheduled Blocks within given radius of lat/lng, up
    to end_date, sorted by date. Block Object defined in Config.
    @radius: distance in kilometres
    @map_data: JSON object with lat/lng coords
    @events: optional list of calendar events
    Returns empty array if none found .
    Returns Error exception on error (invalid KML data).
    '''
    '''
    events = _events || Schedule.getEventsBetween(cal_id, new Date(), end_date)

    eligible_blocks = []

    for i in range(len(map_data.features)):
        try:
            map_name = map_data.features[i].properties.name

            block = Schedule.findBlock(Parser.getBlockFromTitle(map_name), events)

            if block == False:
                continue;

            center = Geo.centerPoint(map_data.features[i].geometry.coordinates[0])

            # Take the first lat/lon vertex in the rectangle and calculate distance
            dist = Geo.distance(lat, lng, center[1], center[0])

            if dist > radius:
                continue;

            if block['date'] <= end_date:
                block['distance'] = dist.toPrecision(2).toString() + 'km'
                eligible_blocks.push(block)
        except Exception as e:
            logger.info(e.name + ': ' + e.message)
            return e

    if len(eligible_blocks) > 0:
        eligible_blocks.sort(function(a, b) {
          if(a.date < b.date)
            return -1
          else if(a.date > b.date)
            return 1
          else
            return 0
        });

        logger.info('Found %s results within radius', str(len(eligible_blocks)))

    return eligible_blocks
    '''

#-------------------------------------------------------------------------------
def center_point(arr):
    '''Returns [x,y] coordinates of center of polygon passed in
    '''

    #var minX, maxX, minY, maxY;
    '''
    for i in range(len(arr)):
        minX = (arr[i][0] < minX || minX == null) ? arr[i][0] : minX
        maxX = (arr[i][0] > maxX || maxX == null) ? arr[i][0] : maxX
        minY = (arr[i][1] < minY || minY == null) ? arr[i][1] : minY
        maxY = (arr[i][1] > maxY || maxY == null) ? arr[i][1] : maxY
    }

    return [(minX + maxX) /2, (minY + maxY) /2]
    '''


#-------------------------------------------------------------------------------
def distance(lat1, lon1, lat2, lon2):
    '''Calculates KM distance between 2 lat/lon coordinates
    '''

    '''
    p = 0.017453292519943295    # Math.PI / 180
    c = Math.cos
    a = 0.5 - c((lat2 - lat1) * p)/2 +
          c(lat1 * p) * c(lat2 * p) *
          (1 - c((lon2 - lon1) * p))/2

    # 2 * R; R = 6371 km
    return 12742 * Math.asin(Math.sqrt(a))
    '''

#-------------------------------------------------------------------------------
def geocode(address, api_key, postal=None, raise_exceptions=False):
    '''Finds best result from Google geocoder given address
    API Reference: https://developers.google.com/maps/documentation/geocoding
    @address: string with address + city + province. Should NOT include postal code.
    @postal: optional arg. Used to identify correct location when multiple
    results found
    Returns:
      -Success: single element list containing result (dict)
      -Empty list [] no result
    Exceptions:
      -Raises requests.RequestException on connection error'''

    try:
        response = requests.get(
          'https://maps.googleapis.com/maps/api/geocode/json',
          params = {
            'address': address,
            'key': api_key
          })
    except requests.RequestException as e:
        logger.error(str(e))
        raise

    #logger.debug(response.text)

    response = json.loads(response.text)

    if response['status'] == 'ZERO_RESULTS':
        e = 'No geocode result for ' + address
        logger.error(e)
        return []
    elif response['status'] == 'INVALID_REQUEST':
        e = 'Invalid request for ' + address
        logger.error(e)
        return []
    elif response['status'] != 'OK':
        e = 'Could not geocode ' + address
        logger.error(e)
        return []

    # Single result

    if len(response['results']) == 1:
        if 'partial_match' in response['results'][0]:
            warning = \
              'Partial match for <strong>%s</strong>. <br>'\
              'Using <strong>%s</strong>.' %(
              address, response['results'][0]['formatted_address'])

            response['results'][0]['warning'] = warning
            logger.debug(warning)

        return response['results']

    # Multiple results

    if postal is None:
        # No way to identify best match. Return 1st result (best guess)
        response['results'][0]['warning'] = \
          'Multiple results for <strong>%s</strong>. <br>'\
          'No postal code. <br>'\
          'Using 1st result <strong>%s</strong>.' % (
          address, response['results'][0]['formatted_address'])

        logger.debug(response['results'][0]['warning'])

        return [response['results'][0]]
    else:
        # Let's use the Postal Code to find the best match
        for idx, result in enumerate(response['results']):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                result['warning'] = \
                  'Multiple results for <strong>%s</strong>.<br>'\
                  'First half of Postal Code <strong>%s</strong> matched in '\
                  'result[%s]: <strong>%s</strong>.<br>'\
                  'Using as best match.' % (
                  address, get_postal(result), str(idx), result['formatted_address'])

                logger.debug(result['warning'])

                return [result]

            # Last result and still no Postal match.
            if idx == len(response['results']) -1:
                response['results'][0]['warning'] = \
                  'Multiple results for <strong>%s</strong>.<br>'\
                  'No postal code match. <br>'\
                  'Using <strong>%s</strong> as best guess.' % (
                  address, response['results'][0]['formatted_address'])

                logger.error(response['results'][0]['warning'])

    return [response['results'][0]]

#-------------------------------------------------------------------------------
def get_postal(geo_result):
    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            return component['short_name']

    return False
