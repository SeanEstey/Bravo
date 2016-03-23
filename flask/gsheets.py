import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import flask
import requests
from datetime import datetime
from flask import request, current_app, render_template
from dateutil.parser import parse

import etap
from app import flask_app, celery_app, db, logger
from config import *

#-------------------------------------------------------------------------------
# scope is array of Google service URL's to authorize
def auth(scope):
    try:
      json_key = json.load(open('oauth_credentials.json'))
      credentials = SignedJwtAssertionCredentials(
        json_key['client_email'],
        json_key['private_key'],
        scope
      )

      return gspread.authorize(credentials)

    except Exception as e:
        logger.info('gsheets.auth():', exc_info=True)
        return False

#-------------------------------------------------------------------------------
def update_entry(status, destination):
    '''Updates the 'Email Status' column in a worksheet
    destination: dict containing 'sheet', 'worksheet', 'row', 'upload_status'
    '''

    try:
        gc = auth(['https://spreadsheets.google.com/feeds'])
        sheet = gc.open(ROUTE_IMPORTER_SHEET)
        wks = sheet.worksheet(destination['worksheet'])
    except Exception as e:
        logger.error(
          'Error opening worksheet %s: %s' ,
          destination['worksheet'], str(e)
        )
        return False

    headers = wks.row_values(1)

    # Make sure the row entry still exists in the worksheet
    # and hasn't been replaced by other data or deleted
    cell = wks.cell(destination['row'], headers.index('Upload Status')+1)

    if not cell:
        logger.error('update_entry cell not found')
        return False

    if str(cell.value) == destination['upload_status']:
        try:
            wks.update_cell(
              destination['row'],
              headers.index('Email Status')+1,
              status
            )
        except Exception as e:
            logger.error(
              'Error writing to worksheet %s: %s',
              destination['worksheet'], str(e)
            )
            return False

    return True

    # Create RFU if event is dropped/bounced and is from a collection receipt
    '''
    if destination['worksheet'] == 'Routes':
        if destination['status'] == 'dropped' or destination['status'] == 'bounced':
            wks = sheet.worksheet('RFU')
            headers = wks.row_values(1)

            rfu = [''] * len(headers)
            rfu[headers.index('Request Note')] = \
                'Email ' + db_record['recipient'] + ' dropped.'

            if 'account_number' in db_record:
              rfu[headers.index('Account Number')] = db_record['account_number']

            logger.info(
              'Creating RFU for bounced/dropped email %s', json.dumps(rfu)
            )

            try:
                wks.append_row(rfu)
            except Exception as e:
                logger.error('Error writing to RFU worksheet: %s', str(e))
                return False
    '''

#-------------------------------------------------------------------------------
def create_rfu(request_note, account_number=None, next_pickup=None, block=None, date=None):
    try:
        gc = auth(['https://spreadsheets.google.com/feeds'])
        sheet = gc.open(ROUTE_IMPORTER_SHEET)
        wks = sheet.worksheet('RFU')
    except Exception as e:
        logger.error('Could not open RFU worksheet: %s', str(e))
        return False

    headers = wks.row_values(1)

    rfu = [''] * len(headers)

    rfu[headers.index('Request Note')] = request_note

    if account_number != None:
      rfu[headers.index('Account Number')] = account_number

    if next_pickup != None:
      rfu[headers.index('Next Pickup Date')] = next_pickup

    if block != None:
      rfu[headers.index('Block')] = block

    if date != None:
      rfu[headers.index('Date')] = date

    logger.info('Creating RFU: ' + json.dumps([item for item in rfu if item]))

    try:
        wks.append_row(rfu)
    except Exception as e:
        logger.error('Could not write to RFU sheet: %s', str(e))
        return False

    return True

#-------------------------------------------------------------------------------
@celery_app.task
def add_signup(signup):
    try:
      gc = auth(['https://spreadsheets.google.com/feeds'])
      wks = gc.open(ROUTE_IMPORTER_SHEET).worksheet('Signups')

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
