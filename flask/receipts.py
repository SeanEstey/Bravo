import json
import logging
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import requests
from datetime import datetime
from dateutil.parser import parse
from flask import render_template

import gsheets
import etap
from app import app, db, info_handler, error_handler, debug_handler
from tasks import celery_app
from config import *
import utils

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------Stuff Todo---------------------------------------
# TODO: Insert db['emails'] document so that email status on Sheet
# can be updated once delivered/bounced


#-------------------------------------------------------------------------------
def on_email_status(webhook):
    '''Forwarded Mailgun webhook on receipt email event.
    Update Sheets accordingly'''

    email = db['emails'].find_one_and_update(
      {'mid': webhook['Message-Id']},
      {'$set': {'status':webhook['event']}})


    if email['on_status']['command'] == 'update_sheet':
        # Update Google Sheets
        try:
            gsheets.update_entry(
              email['agency'],
              webhook['event'],
              email['on_status']['target']
            )
        except Exception as e:
            app.logger.error("Error writing to Google Sheets: " + str(e))
            return 'Failed'

#-------------------------------------------------------------------------------
def send_receipt(agency, account, entry, template, subject):
    '''Sends a receipt/no collection/dropoff followup/etc for a route entry.
    Should be running in process() celery task
    Adds an eTapestry journal note with the content.
    '''

    logger.debug('%s %s', str(account['id']), template)

    if agency == 'vec':
        conf = db['agencies'].find_one({'name':agency})

        body = utils.render_html(template, {
            "entry": entry,
            "from": entry['from'],
            "account": account
        })

        if body == False:
            return False

        # Add Journal note
        etap.call(
            'add_note',
            conf['etapestry'], {
                'id': account['id'],
                'Note': 'Collection Receipt:]\n' + utils.clean_html(body),
                'Date': etap.dt_to_ddmmyyyy(parse(entry['date']))},
            silence_exceptions=True
        )

        logger.debug(response.text)

        mid = utils.send_email(account['email'], subject, body, conf['mailgun'])

        db['emails'].insert({
            'agency': args['agency'],
            'mid': mid,
            'type': 'receipt',
            'status': 'queued',
            'on_status': {
                'command': 'update_sheet',
                # contains worksheet, row, upload_status
                'target': entry['from']
            }
        })
    # Old WSF path
    else:
        try:
            r = requests.post(LOCAL_URL + '/email/send', json={
                "agency": agency,
                "recipient": account['email'],
                "template": template,
                "subject": subject,
                "data": {
                    "entry": entry,
                    "from": entry['from'],
                    "account": account
                }
            })
        except Exception as e:
            logger.error('Failed to send receipt to account ID %s: %s',
            account['id'], str(e))

#-------------------------------------------------------------------------------
@celery_app.task
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
    wks = gc.open(GSHEET_NAME).worksheet('Routes')
    headers = wks.row_values(1)

    num_zeros = 0
    num_drop_followups = 0
    num_cancels = 0
    num_no_emails = 0
    gift_accounts = []

    with open('templates/schemas/'+etapestry_id['agency']+'.json') as json_file:
      schemas = json.load(json_file)['receipts']

    for i in range(0, len(accounts)):
        logger.debug(json.dumps(entries[i]))

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

            entries[i]['date'] = parse(entries[i]['date']).strftime('%B %-d, %Y')

            if 'next_pickup' in entries[i]:
                entries[i]['next_pickup'] = parse(
                        entries[i]['next_pickup']).strftime('%B %-d, %Y')

            # Send Cancelled Receipt
            if etap.get_udf('Status', accounts[i]) == 'Cancelled':
                send_receipt(etapestry_id['agency'], accounts[i], entries[i],
                schemas['cancelled']['file'],
                schemas['cancelled']['subject'])

                num_cancels += 1
                continue

            # If UDF['SMS'] is defined, include it

            # Dropoff Followup Receipt
            drop_date = etap.get_udf('Dropoff Date', accounts[i])

            if drop_date:
                d = drop_date.split('/')
                drop_date = datetime(int(d[2]),int(d[1]),int(d[0])).date()
                collection_date = parse(entries[i]['date']).date()

                if drop_date == collection_date:
                    send_receipt(etapestry_id['agency'],
                        accounts[i],
                        entries[i],
                        schemas['dropoff_followup']['file'],
                        schemas['dropoff_followup']['subject'])

                    num_drop_followups += 1
                    continue

            # Zero Collection Receipt
            if entries[i]['amount'] == 0:
                if entries[i]['next_pickup']:
                    npu = parse(entries[i]['next_pickup']).date()
                    entries[i]['next_pickup'] = npu.strftime('%B %-d, %Y')

                if accounts[i]['nameFormat'] == 3: # Business
                    send_receipt(etapestry_id['agency'],
                         accounts[i],
                         entries[i],
                         schemas['zero_collection']['file'],
                         schemas['zero_collection']['subject'])
                else: # Residential
                    send_receipt(etapestry_id['agency'],
                         accounts[i],
                         entries[i],
                         schemas['no_collection']['file'],
                         schemas['no_collection']['subject'])

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
              etapestry_id, {
                "account_refs": [i['account']['ref'] for i in gift_accounts],
                "start_date": "01/01/" + str(year),
                "end_date": "31/12/" + str(year)
              }
            )

            #logger.info('%s gift histories retrieved', str(len(gift_histories)))

        except Exception as e:
            logger.error('Error retrieving gift histories: %s', str(e))

        for i in range(0, len(gift_accounts)):
            try:
                for a_gift in gift_histories[i]:
                    a_date = parse(a_gift['date'])
                    a_gift['date'] = a_date.strftime('%B %-d, %Y')

                gift_accounts[i]['account']['gift_history'] = gift_histories[i]
                entry = gift_accounts[i]['entry']

                if entry['next_pickup']:
                    npu = parse(entry['next_pickup']).date()
                    entry['next_pickup'] = npu.strftime('%B %-d, %Y')

                send_receipt(
                  etapestry_id['agency'],
                  gift_accounts[i]['account'],
                  gift_accounts[i]['entry'],
                  schemas['collection']['file'],
                  schemas['collection']['subject'])
            except Exception as e:
                logger.error('Error processing gift receipt on row #%s: %s',
                            str(entry['row']), str(e)
                )

    logger.info('Receipts: \n' +
      str(num_zeros) + ' zero collections sent\n' +
      str(len(gift_accounts)) + ' gift receipts sent\n' +
      str(num_drop_followups) + ' dropoff followups sent\n' +
      str(num_cancels) + ' cancellations sent\n' +
      str(num_no_emails) + ' no emails'
    )
