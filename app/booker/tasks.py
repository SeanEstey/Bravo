'''app.booker.tasks'''
import json, os, time
from datetime import datetime
from flask import g
from .. import smart_emit, celery
from app.lib.loggy import Loggy
log = Loggy('booker.tasks', celery_task=True)

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

        log.warning('Task: updating maps...', group=name)

        # download KML file
        os.system(
            'wget \
            "https://www.google.com/maps/d/kml?mid=%s&lid=%s&forcekml=1" \
            -O /tmp/maps.xml' %(conf['mid'], conf['lid']))

        time.sleep(2)

        log.debug('converting KML->geo_json...', group=name)

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
            log.error(desc + str(e), group=name)
            status = 'failed'
        else:
            status = 'success'

            maps = g.db.maps.find_one_and_update(
                {'agency':name},
                {'$set': {
                    'update_dt': datetime.utcnow(),
                    'features': data['features']}})

            desc = 'Task: updated %s maps successfully.' % len(data['features'])

            log.warning(desc, group=name)

        if agcy:
            smart_emit('update_maps',{
                'status': status,
                'description': desc,
                'n_updated': len(maps['features'])})
