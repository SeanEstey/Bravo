'''app.routing.geo'''

import json
import logging
import requests

from app import db

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_gmaps_url(address, lat, lng):
    base_url = 'https://www.google.ca/maps/place/'

    # TODO: use proper urlencode() function here
    full_url = base_url + address.replace(' ', '+')

    full_url +=  '/@' + str(lat) + ',' + str(lng)
    full_url += ',17z'

    return full_url

#-------------------------------------------------------------------------------
def get_postal(geo_result):
    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            return component['short_name']

    return False

#-------------------------------------------------------------------------------
def geocode(address, api_key, postal=None, raise_exceptions=False):
    '''Finds best result from Google geocoder given address
    API Reference: https://developers.google.com/maps/documentation/geocoding
    @address: string with address + city + province. Should NOT include postal code.
    @postal: optional arg. Used to identify correct location when multiple
    results found
    Returns:
      -Success: single element list containing result (dict)
      -Empty list [] no result
    Exceptions:
      -Raises requests.RequestException on connection error'''

    try:
        response = requests.get(
          'https://maps.googleapis.com/maps/api/geocode/json',
          params = {
            'address': address,
            'key': api_key
          })
    except requests.RequestException as e:
        logger.error(str(e))
        raise

    #logger.debug(response.text)

    response = json.loads(response.text)

    if response['status'] == 'ZERO_RESULTS':
        e = 'No geocode result for ' + address
        logger.error(e)
        return []
    elif response['status'] == 'INVALID_REQUEST':
        e = 'Invalid request for ' + address
        logger.error(e)
        return []
    elif response['status'] != 'OK':
        e = 'Could not geocode ' + address
        logger.error(e)
        return []

    # Single result

    if len(response['results']) == 1:
        if 'partial_match' in response['results'][0]:
            warning = \
              'Partial match for <strong>%s</strong>. <br>'\
              'Using <strong>%s</strong>.' %(
              address, response['results'][0]['formatted_address'])

            response['results'][0]['warning'] = warning
            logger.debug(warning)

        return response['results']

    # Multiple results

    if postal is None:
        # No way to identify best match. Return 1st result (best guess)
        response['results'][0]['warning'] = \
          'Multiple results for <strong>%s</strong>. <br>'\
          'No postal code. <br>'\
          'Using 1st result <strong>%s</strong>.' % (
          address, response['results'][0]['formatted_address'])

        logger.debug(response['results'][0]['warning'])

        return [response['results'][0]]
    else:
        # Let's use the Postal Code to find the best match
        for idx, result in enumerate(response['results']):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                result['warning'] = \
                  'Multiple results for <strong>%s</strong>.<br>'\
                  'First half of Postal Code <strong>%s</strong> matched in '\
                  'result[%s]: <strong>%s</strong>.<br>'\
                  'Using as best match.' % (
                  address, get_postal(result), str(idx), result['formatted_address'])

                logger.debug(result['warning'])

                return [result]

            # Last result and still no Postal match.
            if idx == len(response['results']) -1:
                response['results'][0]['warning'] = \
                  'Multiple results for <strong>%s</strong>.<br>'\
                  'No postal code match. <br>'\
                  'Using <strong>%s</strong> as best guess.' % (
                  address, response['results'][0]['formatted_address'])

                logger.error(response['results'][0]['warning'])

    return [response['results'][0]]
