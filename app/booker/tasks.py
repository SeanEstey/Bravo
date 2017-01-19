
import logging
from .. import celery
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task
def update_maps(agency=None, emit_status=False):
    from app.booker import geo

    if agency:
        geo.update_maps(agency, emit_status)
    else:
        for agency in db.agencies.find({}):
            geo.update_maps(agency['name'], emit_status)
