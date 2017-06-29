'''app.main.maps'''
import json, math, os, requests
import matplotlib.path as mplPath
import numpy as np
from flask import g
from app import get_keys
from app.lib.utils import format_bson
from app.main import parser
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def find_block(agcy, address, api_key):

    r = geocode(address, api_key)

    if not r or len(r) == 0:
        log.error('couldnt geocode %s', address)
        return False

    map_name = find_map(agcy, r[0]['geometry']['location'])

    if map_name:
        return map_name[0:map_name.find(' [')]

    return False

#-------------------------------------------------------------------------------
def get_maps(agcy=None):

    g.group = agcy if agcy else g.user.agency
    maps = g.db.maps.find_one({'agency':g.group})
    return format_bson(maps, loc_time=True)

#-------------------------------------------------------------------------------
def in_map(pt, a_map):

    coords = a_map['geometry']['coordinates'][0]

    twod = []
    for c in coords:
        twod.append([c[1],c[0]])

    bbPath = mplPath.Path(np.array(twod))

    if bbPath.contains_point((pt['lat'], pt['lng'])):
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def find_map(agcy, pt):
    '''@pt: {'lng':float, 'lat':float}'''

    log.info('find_map in pt %s', pt)

    maps = g.db.maps.find_one({'agency':agcy})['features']

    for map_ in maps:
        coords = map_['geometry']['coordinates'][0]

        twod = []
        for c in coords:
            twod.append([c[1],c[0]])

        bbPath = mplPath.Path(np.array(twod))

        if bbPath.contains_point((pt['lat'], pt['lng'])):
            print map_['properties']['name']
            return map_['properties']['name']

    log.debug('map not found for pt %s', pt)

    return False

#-------------------------------------------------------------------------------
def get_nearby_blocks(pt, radius, maps, events):
    '''Return list of scheduled Blocks within given radius of lat/lng, up
    to end_date, sorted by date. Block Object defined in Config.
    @pt: {'lng':float, 'lat':float}
    @radius: km
    @maps: geo_json object with lat/lng coords
    @events: gcal event
    Returns:
        list of {'event': gcal_obj, 'distance': float, 'name': str,
        'booked':int}
    Returns empty array if none found .
    Returns Error exception on error (invalid KML data).
    '''

    results = []

    for i in range(len(maps)):
        map_title = maps[i]['properties']['name']
        map_block = parser.get_block(map_title)
        block = None

        # Find the first event matching map block
        for event in events:
            if parser.get_block(event['summary']) == map_block:
                block = {
                    'name': parser.get_block(event['summary']),
                    'event':event}

                break

        if not block:
            continue

        if maps[i]['geometry']['type'] != 'Polygon':
            log.error('map index %s is not a polygon', i)
            continue

        # Take the first lat/lon vertex in the rectangle and calculate distance
        dist = distance(
            pt,
            center_pt(maps[i]['geometry']['coordinates'][0]))

        if dist < radius:
            block['distance'] = str(round(dist,2)) + 'km'
            block['area'] = parser.get_area(event['summary']) or '---'
            block['booked'] = parser.route_size(event['summary']) or '---'
            results.append(block)

    results = sorted(results,
        key=lambda k: k['event']['start'].get('dateTime',k['event']['start'].get('date')))

    log.debug('Found %s Blocks within %s radius', len(results), radius)

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
    '''Google geocoder wrapper. API Ref: https://developers.google.com/maps/documentation/geocoding
    @address: formatted_address
    @postal: helps narrow multiple results (optional)
    Returns: [geolocation_result] on success, [] on fail
    Exceptions:
      -Raises requests.RequestException on connection error'''

    try:
        response = json.loads(requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address':address,'key':api_key}
        ).text)
    except requests.RequestException as e:
        log.error(str(e))
        raise

    if response['status'] != 'OK':
        log.error('Error geocoding %s', address, extra={'response':response})
        return []

    results = response['results']

    # Single result

    if len(results) == 1 and 'partial_match' in results[0]:
        results[0]['warning'] = 'Partial match for %s. Using %s.' % (address, results[0]['formatted_address'])
    if len(results) == 1:
        return [results[0]]

    # Multiple results

    msg = 'Multiple results for %s. Using %s'

    if len(results) > 1 and postal is None:
        results[0]['warning'] = msg % (address, results[0]['formatted_address'])
        return [results[0]]
    elif len(results) > 1 and postal:
        # Narrow results w/ Postal Code
        for idx, result in enumerate(results):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                result['warning'] = msg % (address, result['formatted_address'])
                log.debug(result['warning'])
                return [result]

        results[0]['warning'] = msg % (address, results[0]['formatted_address'])
        log.error(results[0]['warning'])

    return [results[0]]

#-------------------------------------------------------------------------------
def get_postal(geo_result):
    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            return component['short_name']

    return False
