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

ZERO_COLLECTION_EMAIL_SUBJECT = 'We missed your pickup this time around'
DROPOFF_FOLLOWUP_EMAIL_SUBJECT = 'Your Dropoff is Complete'
GIFT_RECEIPT_EMAIL_SUBJECT = 'Thanks for your donation!'
WELCOME_EMAIL_SUBJECT = 'Welcome to Empties to Winn'
CANCELLED_EMAIL_SUBJECT = 'You have been removed from the collection schedule'

#-------------------------------------------------------------------------------
def send(account, entry, template, subject):
    try:
        r = requests.post(PUB_URL + '/email/send', json={
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

    logger.info(r.text)

#-------------------------------------------------------------------------------
@celery_app.task
def process(entries, keys):
    '''Celery process that sends email receipts to entries in Route
    Importer->Routes worksheet. Lots of account data retrieved from eTap
    (accounts + journal data) so can take awhile to run 4 templates:
    gift_collection, zero_collection, dropoff_followup, cancelled entries:
    list of row entries to receive emailed receipts
    '''

    try:
        # Get all eTapestry account data
        accounts = etap.call('get_accounts', keys, {
          "account_numbers": [i['account_number'] for i in entries]
        })
    except Exception as e:
        logger.error('Error retrieving accounts from etap')
        return False

    # Update 'Email Status' with either 'queued' or 'no email' so user knows
    # process is running
    #gc = auth(['https://spreadsheets.google.com/feeds'])
    #wks = gc.open('Route Importer').worksheet('Routes')
    #headers = wks.row_values(1)
    #start = wks.get_addr_int(2, headers.index('Email Status')+1)
    #end = start[0] + str(len(accounts)+1)
    #status_range = wks.range(start + ':' + end)

    num_zeros = 0
    num_drop_followups = 0
    num_cancels = 0
    gift_accounts = []

    for i in range(0, len(accounts)):
        if 'email' not in accounts[i]:
            continue

        # Cancelled Receipt
        if etap.get_udf('Status', accounts[i]) == 'Cancelled':
            send(accounts[i], entries[i], "email_cancelled.html",
                    CANCELLED_EMAIL_SUBJECT)

            num_cancels += 1

        # Dropoff Followup Receipt
        drop_date = etap.get_udf('Dropoff Date', accounts[i])

        if drop_date:
            d = drop_date.split('/')
            drop_date = datetime(int(d[2]),int(d[1]),int(d[0])).date()
            collection_date = parse(entries[i]['date']).date()

            if drop_date == collection_date:
                send(accounts[i], entries[i], "email_dropoff_followup.html",
                        DROPOFF_FOLLOWUP_EMAIL_SUBJECT)

                num_drop_followups += 1

        # Zero Collection Receipt
        if entries[i]['amount'] == 0:
            if entries[i]['next_pickup']:
                npu = parse(entries[i]['next_pickup']).date()
                entries[i]['next_pickup'] = npu.strftime('%B %-d, %Y')

            send(accounts[i], entries[i], "email_zero_collection.html",
                    ZERO_COLLECTION_EMAIL_SUBJECT)

            num_zeros +=1

        # Gift Receipt
        elif entries[i]['amount'] > 0:
            gift_accounts.append({'entry': entries[i], 'account': accounts[i]})

    # All receipts sent except Gifts. Query Journal Histories

    if len(gift_accounts) > 0:
        year = parse(gift_accounts[0]['entry']['date']).year

        gift_histories = etap.call('get_gift_histories', keys, {
          "account_refs": [i['account']['ref'] for i in gift_accounts],
          "start_date": "01/01/" + str(year),
          "end_date": "31/12/" + str(year)
        })

        for i in range(0, len(gift_accounts)):
            gift_accounts[i]['account']['gift_history'] = gift_histories[i]
            entry = gift_accounts[i]['entry']

            if entry['next_pickup']:
                npu = parse(entry).date()
                entry['next_pickup'] = npu.strftime('%B %-d, %Y')

            send(gift_accounts[i]['account'], gift_accounts[i]['entry'],
            "email_collection_receipt.html", GIFT_RECEIPT_EMAIL_SUBJECT)

    logger.info('Receipts: \n' +
      str(num_zeros) + ' zero collections sent\n' +
      str(len(gift_accounts)) + ' gift receipts sent\n' +
      str(num_drop_followups) + ' dropoff followups sent\n' +
      str(num_cancels) + ' cancellations sent'
    )
