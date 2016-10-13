'''notify.notifics'''

import twilio
from flask import render_template, current_app
import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
import requests
from pymongo.collection import ReturnDocument
from bson.objectid import ObjectId
import bson.json_util
import json
import re

from .. import mailgun, gsheets, utils, etap
from .. import db
from . import voice, sms, email

logger = logging.getLogger(__name__)

#-------------------------------Stuff Todo---------------------------------------
# TODO: add sms template files
# TODO: include date in email subject

#-------------------------------------------------------------------------------
def insert(evnt_id, event_dt, trig_id, acct_id, _type, to, content):
    '''Add a notification tied to an event and trigger
    @evnt_id: _id of db.notific_events document
    @trig_id: _id of db.triggers document
    @acct_id: _id of db.accounts document
    @type: one of ['sms', 'voice', 'email']
    @to: phone number or email
    @content:
        'source': 'template/audio_url',
        'template': {'default':{'file':'path', 'subject':'email_sub'}}
        'audio_url': 'url'
    Returns:
      -id (ObjectId)
    '''

    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
        'status': 'pending',
        'attempts': 0,
        'to': to,
        'type': _type,
        'on_answer': content,
        'opted_out': False
    }).inserted_id

#-------------------------------------------------------------------------------
def send(notification, agency_conf):
    '''TODO: store conf data for twilio or mailgun when created, not on
    send()
    '''

    if notification['status'] != 'pending':
        return False

    logger.debug('Sending %s', notification['type'])

    if notification['type'] == 'voice':
        return voice.call(notification, agency_conf['twilio'])
    elif notification['type'] == 'sms':
        return sms.send(notification, agency_conf['twilio'])
    elif notification['type'] == 'email':
        return email.send(notification, agency_conf['mailgun'])

#-------------------------------------------------------------------------------
def edit(acct_id, fields):
    '''User editing a notification value from GUI
    '''
    for fieldname, value in fields:
        if fieldname == 'udf.pickup_dt':
          try:
            value = parse(value)
          except Exception, e:
            logger.error('Could not parse event_dt in /edit/call')
            return '400'

        db['accounts'].update({'_id':acct_id}, {'$set':{fieldname:value}})

        # update notification 'to' fields if phone/email edited
        if fieldname == 'email':
            db['notifics'].update_one(
                {'acct_id':acct_id},
                {'$set':{'to':value}})
        elif fieldname == 'phone':
            db['notifics'].update_one(
                {'acct_id':acct_id, '$or': [{'type':'voice'},{'type':'sms'}]},
                {'$set': {'to':value}})

        logger.info('Editing ' + fieldname + ' to value: ' + str(value))

        return True
