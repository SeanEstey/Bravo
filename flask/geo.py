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
