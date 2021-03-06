'''app.booker.tasks'''
import json, os, time
from datetime import datetime
from flask import g
from .. import celery
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task
def update_maps(group=None, **rest):
    '''TODO: if group != None, called from API. send socketio emit on complete
    '''

    if group:
        groups = [g.db['groups'].find_one({'name':group})]
    else:
        groups = list(g.db['groups'].find({}))

    for group_ in groups:
        g.group = group_['name']
        status = desc = None
        conf = g.db.maps.find_one({'agency':g.group})

        log.info('Task: updating maps...')

        # download KML file
        os.system(
            'wget \
            "https://www.google.com/maps/d/kml?mid=%s&lid=%s&forcekml=1" \
            -O /tmp/maps.xml' %(conf['mid'], conf['lid']))

        time.sleep(2)

        log.debug('converting KML->geo_json...')

        # convert to geo_json
        os.system('togeojson /tmp/maps.xml > /tmp/maps.json')

        time.sleep(2)

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
                {'agency':g.group},
                {'$set': {
                    'update_dt': datetime.utcnow(),
                    'features': data['features']}})

            desc = 'Updated %s maps successfully' % len(data['features'])

            log.info(desc, extra={'map_id':maps['mid']})

        if group:
            pass
            #smart_emit('update_maps',{
            #    'status': status,
            #    'description': desc,
            #    'n_updated': len(maps['features'])})
