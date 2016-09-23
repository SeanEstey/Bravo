import logging
import matplotlib.path as mplPath
import numpy as np

from config import *
from routing import geocode

from app import app,db,info_handler,error_handler,debug_handler,socketio

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
def find_block(address):
    r = geocode(address)

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


#-------------------------------------------------------------------------------
def center_point(arr):
    '''Returns [x,y] coordinates of center of polygon passed in
    '''

    #var minX, maxX, minY, maxY;

    for i in range(len(arr)):
        minX = (arr[i][0] < minX || minX == null) ? arr[i][0] : minX
        maxX = (arr[i][0] > maxX || maxX == null) ? arr[i][0] : maxX
        minY = (arr[i][1] < minY || minY == null) ? arr[i][1] : minY
        maxY = (arr[i][1] > maxY || maxY == null) ? arr[i][1] : maxY
    }

    return [(minX + maxX) /2, (minY + maxY) /2]


#-------------------------------------------------------------------------------
def distance(lat1, lon1, lat2, lon2):
    '''Calculates KM distance between 2 lat/lon coordinates
    '''

    p = 0.017453292519943295    # Math.PI / 180
    c = Math.cos
    a = 0.5 - c((lat2 - lat1) * p)/2 +
          c(lat1 * p) * c(lat2 * p) *
          (1 - c((lon2 - lon1) * p))/2

    # 2 * R; R = 6371 km
    return 12742 * Math.asin(Math.sqrt(a))
