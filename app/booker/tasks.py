'''app.booker.tasks'''
import json, logging, os, time
from datetime import datetime
from flask import g
from app import task_logger
from .. import smart_emit, celery
log = task_logger(__name__)

#-------------------------------------------------------------------------------
@celery.task
def update_maps(agcy=None, **rest):
    '''TODO: if agcy != None, called from API. send socketio emit on complete
    '''

    if agcy:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = list(g.db.agencies.find({}))

    for agency in agencies:
        status = desc = None
        name = agency['name']
        conf = g.db.maps.find_one({'agency':name})

        log.debug('downloading kml file...')

        # download KML file
        os.system(
            'wget \
            "https://www.google.com/maps/d/kml?mid=%s&lid=%s&forcekml=1" \
            -O /tmp/maps.xml' %(conf['mid'], conf['lid']))

        time.sleep(2)

        log.debug('converting to geo_json...')

        # convert to geo_json
        os.system('togeojson /tmp/maps.xml > /tmp/maps.json')

        time.sleep(2)

        log.debug('loading geo_json...')

        try:
            with open(os.path.join('/tmp', 'maps.json')) as data_file:
                data = json.load(data_file)
        except Exception as e:
            desc = \
                'problem opening maps.json. may be issue either '\
                'downloading .xml file or conversion to .json. '
            log.error(desc + str(e))
            status = 'failed'
        else:
            status = 'success'

            maps = g.db.maps.find_one_and_update(
                {'agency':name},
                {'$set': {
                    'update_dt': datetime.utcnow(),
                    'features': data['features']
                }}
            )

            desc = 'Updated %s maps successfully.' % len(data['features'])

            log.info('%s: %s', name, desc)

        if agcy:
            smart_emit('update_maps',{
                'status': status,
                'description': desc,
                'n_updated': len(maps['features'])})
