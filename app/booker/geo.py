import logging
import matplotlib.path as mplPath
import numpy as np
import math
import requests
import json

from app import db
from .. import parser

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def find_block(address, api_key):
    r = geocode(address, api_key)

    if not r or len(r) == 0:
        logger.error('couldnt geocode %s', address)
        return False

    map_name = find_map(r[0]['geometry']['location'])

    if map_name:
        return map_name[0:map_name.find(' [')]

    return False

#-------------------------------------------------------------------------------
def find_map(pt):
    '''@pt: {'lng':float, 'lat':float}'''

    logger.info('find_map in pt %s', pt)

    maps = db.maps.find_one({})['features']

    for map_ in maps:
        coords = map_['geometry']['coordinates'][0]

        twod = []
        for c in coords:
            twod.append([c[1],c[0]])

        bbPath = mplPath.Path(np.array(twod))

        if bbPath.contains_point((pt['lat'], pt['lng'])):
            print map_['properties']['name']
            return map_['properties']['name']

    logger.debug('map not found for pt %s', pt)

    return False


#-------------------------------------------------------------------------------
def get_nearby_blocks(pt, radius, maps, events):
    '''Return list of scheduled Blocks within given radius of lat/lng, up
    to end_date, sorted by date. Block Object defined in Config.

    @pt: {'lng':float, 'lat':float}
    @radius: km
    @maps: geo_json object with lat/lng coords
    @events: gcal event

    Returns empty array if none found .
    Returns Error exception on error (invalid KML data).
    '''

    results = []

    for i in range(len(maps['features'])):
        map_title = maps['features'][i]['properties']['name']
        map_block = parser.get_block(map_title)
        block = None

        # Find the first event matching map block
        for event in events:
            if parser.get_block(event['summary']) == map_block:
                block = {
                    'name': parser.get_block(event['summary']),
                    'event':event
                }

                break

        if not block:
            continue

        # Take the first lat/lon vertex in the rectangle and calculate distance
        dist = distance(
            pt,
            center_pt(maps['features'][i]['geometry']['coordinates'][0]))

        if dist < radius:
            block['distance'] = str(round(dist,2)) + 'km'
            results.append(block)

    results = sorted(
        results,
        key=lambda k: k['event']['start'].get('dateTime',k['event']['start'].get('date'))
    )

    logger.info('Found %s results within radius', str(len(results)))

    for block in results:
        logger.info(
            '%s: %s (%s away)',
            block['event']['start'].get('dateTime', block['event']['start'].get('date')),
            block['name'],
            block['distance'])

    return results

#-------------------------------------------------------------------------------
def center_pt(arr):
    '''Returns [x,y] coordinates of center of polygon passed in
    @arr: geo_json list of [lng,lat] representing polygon
    '''

    minX = None
    minY = None
    maxX = None
    maxY = None

    for i in range(len(arr)):
        minX = arr[i][0] if (arr[i][0] < minX or not minX) else minX
        maxX = arr[i][0] if (arr[i][0] > maxX or not maxX) else maxX
        minY = arr[i][1] if (arr[i][1] < minY or not minY) else minY
        maxY = arr[i][1] if (arr[i][1] > maxY or not maxY) else maxY

    return {'lng':(minX + maxX) /2, 'lat':(minY + maxY) /2}

#-------------------------------------------------------------------------------
def distance(pt1, pt2):
    '''Calculates KM distance between 2 lat/lon coordinates
    '''

    p = 0.017453292519943295    # Math.PI / 180
    c = math.cos
    a = 0.5 - c((pt2['lat'] - pt1['lat']) * p)/2 + \
          c(pt1['lat'] * p) * c(pt2['lat'] * p) * \
          (1 - c((pt2['lng'] - pt1['lng']) * p))/2

    # 2 * R; R = 6371 km
    return 12742 * math.asin(math.sqrt(a))

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
