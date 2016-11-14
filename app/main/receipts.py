'''app.main.receipts'''

import json
import logging
import os
import gspread
import requests
from flask import current_app, request
from datetime import datetime, date
from dateutil.parser import parse
from flask import render_template, request

from .. import html, mailgun, etap, gsheets
from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    logger.info('receipt delivered to %s', request.form['recipient'])

    email = db['emails'].find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    gsheets.update_entry(
      email['agency'],
      request.form['event'],
      email['on_status']['update']
    )

#-------------------------------------------------------------------------------
def on_dropped():
    '''Mailgun webhook called from view. Has request context'''

    msg = 'receipt to %s dropped. %s. %s' %(
        request.form['recipient'],
        request.form['reason'],
        request.form.get('description'))

    logger.info(msg)

    email = db['emails'].find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    gsheets.update_entry(
      email['agency'],
      request.form['event'],
      email['on_status']['update']
    )

    from .. import tasks
    tasks.rfu.apply_async(
        args=[email['agency'], msg],
        kwargs={'_date': date.today().strftime('%-m/%-d/%Y')},
        queue=current_app.config['DB']
    )

#-------------------------------------------------------------------------------
def render_body(template_file, data):
    '''Convert all dates in data to long format strings, render into html'''

    # Bravo php returned gift histories as ISOFormat
    if data.get('history'):
        for gift in data['history']:
            gift['date'] = parse(gift['date']).strftime('%B %-d, %Y')

    # Entry dates are in ISOFormat string. Convert to long format
    if data.get('entry'):
        data['entry']['date'] = parse(data['entry']['date']).strftime('%B %-d, %Y')

        if data['entry'].get('next_pickup'):
            npu = parse(data['entry']['next_pickup'])
            data['entry']['next_pickup'] = npu.strftime('%B %-d, %Y')

    with current_app.test_request_context():
        current_app.config['SERVER_NAME'] = os.environ.get('BRAVO_HTTP_HOST')
        try:
            body = render_template(
                template_file,
                to = data['account']['email'],
                account = data['account'],
                entry = data['entry'],
                history = data.get('history'), # optional
                http_host= os.environ.get('BRAVO_HTTP_HOST')
            )
        except Exception as e:
            logger.error('render receipt template: %s', str(e))
            current_app.config['SERVER_NAME'] = None
            return False
        current_app.config['SERVER_NAME'] = None

    return body

#-------------------------------------------------------------------------------
def send(agency, to, template, subject, data):
    '''Sends a receipt/no collection/dropoff followup/etc for a route entry.
    Should be running in process() celery task
    Adds an eTapestry journal note with the content.
    '''

    logger.debug('%s %s', str(data['account']['id']), template)

    agency_conf = db['agencies'].find_one({'name':agency})

    body = render_body(template, data=data)

    if body == False:
        return False

    # Add Journal note
    etap.call(
        'add_note',
        agency_conf['etapestry'],
        data={
            'id': data['account']['id'],
            'Note': 'Receipt:\n' + html.clean_whitespace(body),
            'Date': etap.dt_to_ddmmyyyy(parse(data['entry']['date']))
        },
        silence_exceptions=False
    )

    mid = mailgun.send(
        to, subject, body, agency_conf['mailgun'],
        v={'type':'receipt'})

    db.emails.insert_one({
        'agency': agency,
        'mid': mid,
        'type': 'receipt',
        'on_status': {
            'update': data['entry']['from']
            }
    })


#-------------------------------------------------------------------------------
def process(entries, etapestry_id):
    '''Celery process that sends email receipts to entries in Bravo
    Sheets->Routes worksheet. Lots of account data retrieved from eTap
    (accounts + journal data) so can take awhile to run 4 templates:
    gift_collection, zero_collection, dropoff_followup, cancelled entries:
    list of row entries to receive emailed receipts
    @entries: array of gift entries
    @etapestry_id: agency name and login info
    TODO: replace etapestry_id with agency name. Lookup etap_id from DB
    '''

    try:
        # Get all eTapestry account data.
        # List is indexed the same as @entries arg list
        accounts = etap.call('get_accounts', etapestry_id, {
          "account_numbers": [i['account_number'] for i in entries]
        })
    except Exception as e:
        logger.error('Error retrieving accounts from etap: %s', str(e))
        return False

    oauth = db['agencies'].find_one({'name':etapestry_id['agency']})['google']['oauth']
    gc = gsheets.auth(oauth, ['https://spreadsheets.google.com/feeds'])
    wks = gc.open(current_app.config['GSHEET_NAME']).worksheet('Routes')
    headers = wks.row_values(1)

    num_zeros = 0
    num_drop_followups = 0
    num_cancels = 0
    num_no_emails = 0
    gift_accounts = []

    with open('app/templates/schemas/'+etapestry_id['agency']+'.json') as json_file:
      schemas = json.load(json_file)['receipts']

    agency = etapestry_id['agency']

    for i in range(0, len(accounts)):
        try:
            if not accounts[i]['email']:
                wks.update_cell(
                  entries[i]['from']['row'],
                  headers.index('Email Status')+1,
                  'no email'
                )
                num_no_emails += 1

                continue
            else:
                wks.update_cell(
                  entries[i]['from']['row'],
                  headers.index('Email Status')+1,
                  'queued'
                )

            # Send Cancelled Receipt
            if etap.get_udf('Status', accounts[i]) == 'Cancelled':
                send(
                    agency,
                    accounts[i]['email'],
                    "receipts/"+agency+"/cancelled.html",
                    "Your Account has been Cancelled",
                    data={
                        'account': accounts[i],
                        'entry': entries[i]
                    })

                num_cancels += 1
                continue

            # If UDF['SMS'] is defined, include it

            # Dropoff Followup Receipt
            drop_date = etap.get_udf('Dropoff Date', accounts[i])

            if drop_date:
                if etap.ddmmyyyy_to_date(drop_date) == parse(entries[i]['date']).date():
                    send(
                        agency,
                        accounts[i]['email'],
                        "receipts/"+agency+"/dropoff_followup.html",
                        "Dropoff Complete",
                        data={
                            'account': accounts[i],
                            'entry': entries[i]
                        })

                    num_drop_followups += 1
                    continue

            # Zero Collection Receipt
            if entries[i]['amount'] == 0:
                if accounts[i]['nameFormat'] == 3: # Business
                    send(
                        agency,
                        accounts[i]['email'],
                        "receipts/"+agency+"/zero_collection.html",
                        "See you next time",
                        data={
                            'account': accounts[i],
                            'entry': entries[i]
                        })

                else: # Residential
                    send(
                        agency,
                        accounts[i]['email'],
                        "receipts/"+agency+"/no_collection.html",
                        "See you next time",
                        data={
                            'account': accounts[i],
                            'entry': entries[i]
                        })

                num_zeros +=1

            # Gift Receipt
            elif entries[i]['amount'] > 0:
                gift_accounts.append({'entry': entries[i], 'account': accounts[i]})

        except Exception as e:
            logger.error('Receipt error. Row %s: %s',str(entries[i]['from']['row']), str(e))

        # All receipts sent except Gifts. Query Journal Histories

    if len(gift_accounts) > 0:
        try:
            year = parse(gift_accounts[0]['entry']['date']).year

            gift_histories = etap.call(
                'get_gift_histories',
                etapestry_id,
                data={
                    "account_refs": [i['account']['ref'] for i in gift_accounts],
                    "start_date": "01/01/" + str(year),
                    "end_date": "31/12/" + str(year)
                })
            logger.info('%s gift histories retrieved', str(len(gift_histories)))

        except Exception as e:
            logger.error('Error retrieving gift histories: %s', str(e))

        for i in range(0, len(gift_accounts)):
            try:
                logger.debug('gift_history: %s', str(gift_histories[i]))

                send(
                    agency,
                    gift_accounts[i]['account']['email'],
                    "receipts/"+agency+"/collection_receipt.html",
                    "Thanks for your Donation",
                    data={
                        'account': gift_accounts[i]['account'],
                        'entry': gift_accounts[i]['entry'],
                        'history': gift_histories[i]
                    })

            except Exception as e:
                logger.error('Error processing gift receipt on row #%s: %s',
                            str(gift_accounts[i]['entry']['from']['row']), str(e)
                )

    logger.info('Receipts: \n' +
      str(num_zeros) + ' zero collections sent\n' +
      str(len(gift_accounts)) + ' gift receipts sent\n' +
      str(num_drop_followups) + ' dropoff followups sent\n' +
      str(num_cancels) + ' cancellations sent\n' +
      str(num_no_emails) + ' no emails')
