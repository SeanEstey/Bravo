import json
from datetime import datetime
from flask import current_app
import logging

from . import gsheets
from . import db

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def resolve_depot(block, postal_codes, event_desc=False):
    '''Find correct depot for given Block.
    First see if 'routing.depots' has defined this Block belongs to it.
    Next see if Google Cal Event Desc defines a depot.
    Last, see if 'routing.depots' postal_codes match ones given.
    Return 'Strathcona' as default if none found.
    '''

    depots = list(db['agencies'].find_one({'name':'wsf'})['routing']['depots'])

    for depot in depots:
        # The block defined under depot in list?
        if depot.get('blocks') and block in depot['blocks']:
            return depot

        # Depot defined in Calendar Event desc?
        if event_desc and event_desc.find(depot['name']) > -1:
            return depot

    # Depot not explicitly defined.
    # Do postal code lookup
    for depot in depots:
        if not depot.get('postal_codes'):
            continue

        if set(depot['postal_codes']) & set(postal_codes):
            return depot

    # Still haven't found depot. Use Strathcona as default
    logger.error(
        'No depot defined for Block %s. '\
        'Postal codes: [%s]. Using Strathcona as default.',
        block, postal_codes)

    for depot in depots:
        if depot['name'] == 'Strathcona':
            return depot


#-------------------------------------------------------------------------------
#@celery_app.task
def add_signup(signup):
    '''Called by emptiestowinn.com signup form only for now
    '''

    logger.info('New signup received: %s %s',
      signup.get('first_name'),
      signup.get('last_name')
    )

    try:
      oauth = db['agencies'].find_one({'name':'wsf'})['google']['oauth']
      gc = gsheets.auth(oauth, ['https://spreadsheets.google.com/feeds'])
      wks = gc.open(current_app.config['GSHEET_NAME']).worksheet('Signups')

      form_data = {
        'Signup Date': datetime.now().strftime('%-m/%-d/%Y'),
        'Office Notes': signup['special_requests'],
        'Address': signup['address'],
        'Postal Code': signup['postal'],
        'Primary Phone': signup['phone'],
        'Email': signup['email'],
        'Tax Receipt': signup['tax_receipt'],
        'Reason Joined': signup['reason_joined'],
        'City': signup['city'],
        'Status': 'Dropoff'
      }

      if signup['account_type'] == 'Residential':
          form_data['First Name'] = signup['first_name']
          form_data['Last Name'] = signup['last_name']
          form_data['Name Format'] = 'Individual'
          form_data['Persona Type'] = 'Personal'
      elif signup['account_type'] == 'Business':
          form_data['Business Name'] = signup['account_name']
          form_data['Contact Person'] = signup['contact_person']
          form_data['Name Format'] = 'Business'
          form_data['Persona Type'] = 'Business'

      if 'title' in signup:
        form_data['Title'] = signup['title']

      if 'referrer' in signup:
        form_data['Referrer'] = signup['referrer']

      headers = wks.row_values(1)
      row = []

      for field in headers:
        if form_data.has_key(field):
          row.append(form_data[field])
        else:
          row.append('')

      wks.append_row(row)

    except Exception, e:
      logger.info('add_signup. data: ' + json.dumps(signup), exc_info=True)
      return str(e)

    return True
