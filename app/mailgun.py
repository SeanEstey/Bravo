'''app.mailgun'''

import requests
import json
import logging

logger = logging.getLogger(__name__)

# TODO: rename all "send_email" calls to "mailgun.send"


#-------------------------------------------------------------------------------
def send(to, subject, body, conf, v=None):
    '''Send email via mailgun.
    @conf: db.agencies.mailgun
    @v: custom dict to included in webhooks
    Returns:
      -mid string on success
    '''

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data={
            'from': conf['from'],
            'to':  to,
            'subject': subject,
            'html': body,
            'v': json.dumps(v)
        })
    except requests.RequestException as e:
        logger.error('mailgun: %s ', str(e))
        return False

    logger.debug(response.text)

    return json.loads(response.text)['id']

