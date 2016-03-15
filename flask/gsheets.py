import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import flask
import requests
from datetime import datetime
from flask import request, current_app, render_template
from dateutil.parser import parse

import scheduler
import etap
from app import flask_app, celery_app, db, logger
from config import *

#-------------------------------------------------------------------------------
# scope is array of Google service URL's to authorize
def auth(scope):
    try:
      json_key = json.load(open('oauth_credentials.json'))
      credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
      return gspread.authorize(credentials)
    except Exception as e:
      logger.info('gsheets.auth():', exc_info=True)
      return False

#-------------------------------------------------------------------------------
def update_entry(db_record):
    gc = auth(['https://spreadsheets.google.com/feeds'])
    sheet = gc.open(db_record['sheet_name'])
    wks = sheet.worksheet(db_record['worksheet_name'])
    headers = wks.row_values(1)
    
    # Make sure the row entry still exists in the worksheet
    cell = wks.cell(db_record['row'], headers.index('Upload Status')+1)
  
    if cell:
      if str(cell.value) == db_record['upload_status']:
        wks.update_cell(db_record['row'], headers.index('Email Status')+1, db_record['status'])
  
    # Create RFU if event is dropped/bounced and is from a collection receipt
    if db_record['worksheet_name'] == 'Routes':
        if db_record['status'] == 'dropped' or db_record['status'] == 'bounced':
            wks = sheet.worksheet('RFU')
            headers = wks.row_values(1)
            
            rfu = [''] * len(headers)
            rfu[headers.index('Request Note')] = 'Email ' + db_record['recipient'] + ' dropped.'
    
            if 'account_number' in db_record:
              rfu[headers.index('Account Number')] = db_record['account_number']
    
            logger.info('Creating RFU for bounced/dropped email: ' + json.dumps(rfu))
            wks.append_row(rfu)

#-------------------------------------------------------------------------------
def create_rfu(request_note, account_number=None, next_pickup=None, block=None, date=None):
    gc = auth(['https://spreadsheets.google.com/feeds'])
    sheet = gc.open('Route Importer')
    wks = sheet.worksheet('RFU')
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
    wks.append_row(rfu)

#-------------------------------------------------------------------------------
@celery_app.task
def add_signup_row(signup):
    try:
      gc = auth(['https://spreadsheets.google.com/feeds'])
      wks = gc.open('Route Importer').worksheet('Signups')
  
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
      logger.info('add_signup_row. data: ' + json.dumps(signup), exc_info=True)
      return str(e)
