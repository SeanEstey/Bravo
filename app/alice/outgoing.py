'''app.alice.outgoing'''

import logging
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException
from .. import get_db
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def compose(body, to, agency, conf, callback=None):
    '''Compose SMS message to recipient
    Can be called from outside blueprint. No access to flask session
    '''

    self_name = get_self_name(agency)

    if self_name:
        body = '%s: %s' % (self_name, body)

    try:
        client = TwilioRestClient(
            conf['api']['sid'],
            conf['api']['auth_id'])
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise

    try:
        msg = client.messages.create(
            body = body,
            to = to,
            from_ = conf['sms']['number'],
            status_callback = callback)
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise
    else:
        log.info('returning msg')
        return msg

    log.info('returning msg status')
    return msg.status

#-------------------------------------------------------------------------------
def get_self_name(agency):
    db = get_db()
    return db.agencies.find_one({'name':agency})['alice']['name']
