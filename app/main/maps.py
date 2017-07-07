# app.main.maps

import json, logging, math, os, requests
import matplotlib.path as mplPath
import numpy as np
from flask import g
from app import get_keys
from app.lib.utils import format_bson
from app.main import parser
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
class GeocodeError(Exception):
    def __init__(self, message, **kwargs):
        Exception.__init__(self, message)
        for kw in kwargs:
            if kw == 'message':
                continue
            setattr(self, kw, kwargs[kw])

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
def build_url(address, lat, lng):
    base_url = 'https://www.google.ca/maps/place/'

    # TODO: use proper urlencode() function here
    full_url = base_url + address.replace(' ', '+')

    full_url +=  '/@' + str(lat) + ',' + str(lng)
    full_url += ',17z'

    return full_url

#-------------------------------------------------------------------------------
def find_block(group, address, api_key):

    r = geocode(address, api_key)

    if not r or len(r) == 0:
        log.error('couldnt geocode %s', address)
        return False

    map_name = find_map(group, r[0]['geometry']['location'])

    if map_name:
        return map_name[0:map_name.find(' [')]

    return False

#-------------------------------------------------------------------------------
def get_maps(group=None):

    g.group = group if group else g.group
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
def find_map(group, pt):
    '''@pt: {'lng':float, 'lat':float}'''

    log.info('find_map in pt %s', pt)

    maps = g.db.maps.find_one({'agency':group})['features']

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
def get_postal(geo_result):
    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            return component['short_name']

    return False
