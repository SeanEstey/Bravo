import json

from config import *

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

def send_to_routific(block):

    # Get data from route via eTap API
    # stops = etap.call('
    accounts = etap.call('get_query_accounts', keys, {
      "query": block,
      "query_category": "ETW: Routes"
    })

    # TODO: Convert to Routific JSON format

    routific = json.dumps(accounts)

    url = 'https://api.routific.com/v1/vrp'
    headers = {
        'content-type': 'application/json',
        'Authorization': ROUTIFIC_KEY
    }

    try:
        r = requests.post(
            url,
            headers=headers,
            data=json.dumps(accounts)
        )
    except Exception as e:
        logger.error(e)
        return False

    return True
