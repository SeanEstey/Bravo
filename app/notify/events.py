'''app.notify.events'''
import pytz
from datetime import datetime,date,time
from dateutil.parser import parse
from bson.objectid import ObjectId as oid
from flask import g, request, jsonify, url_for
from app import get_keys
from app.main import cal, parser
from app.main.parser import is_res, is_bus
from app.lib.utils import format_bson
from app.lib.dt import to_utc, to_local
from . import triggers
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def create_event():
    '''Called via API
    '''

    from app.notify.pickups import create_reminder
    from app.notify import gg, voice_announce

    tmplt = request.form['template_name']

    if tmplt == 'green_goods':
        try:
            evnt_id = gg.add_event()
        except Exception as e:
            #log.error(str(e))
            #log.debug('', exc_info=True)
            raise
    elif tmplt == 'recorded_announcement':
        try:
            evnt_id = voice_announce.add_event()
        except Exception as e:
            log.exception('Error creating event')
            raise
    elif tmplt == 'bpu':
        block = request.form['query_name']

        if is_bus(block):
            cal_id = get_keys('cal_ids').get('bus') or get_keys('cal_ids').get('routes')
        else:
            cal_id = get_keys('cal_ids').get('res') or get_keys('cal_ids').get('routes')

        oauth = get_keys('google')['oauth']
        date_ = cal.get_next_block_date(cal_id, block, oauth)

        try:
            evnt_id = create_reminder(g.user.agency, block, date_)
        except Exception as e:
            log.exception('Error creating pick-up event')
            raise

    event = g.db.events.find_one({'_id':evnt_id})
    event['triggers'] = get_triggers(event['_id'])

    for trigger in event['triggers']:
        # modifying 'triggers' structure for view rendering
        trigger['count'] = triggers.get_count(trigger['_id'])

    log.warning('Created notification event %s.', event['name'],
        extra={'type':event['type']})

    return {
        'event': format_bson(event, loc_time=True),
        'description':
            'Reminders for event %s successfully scheduled.' %
            (request.form['query_name']),
        'view_url': url_for('notify.view_event', evnt_id=str(event['_id'])),
        'cancel_url': url_for('api._cancel_event', evnt_id=str(event['_id']))}

#-------------------------------------------------------------------------------
def cancel_event(evnt_id=None):
    '''Called via API. Remove all triggers, notifics, and event from DB
    '''

    evnt_id = oid(evnt_id)
    evnt = g.db.events.find_one({'_id':evnt_id})
    notifics = g.db.notifics.find({'evnt_id':evnt_id})

    n_accts = 0

    for notific in notifics:
        n_accts += g.db.accounts.remove({'_id':notific['acct_id']}).get('n')

    n_notifics = g.db.notifics.remove({'evnt_id':evnt_id}).get('n')
    n_triggers = g.db.triggers.remove({'evnt_id': evnt_id}).get('n')
    n_events = g.db.events.remove({'_id': evnt_id}).get('n')

    log.info('Cancelled event %s', evnt['name'], extra={
        'n_del_notific':n_notifics,
        'n_del_triggers': n_triggers,
        'n_del_accounts': n_accts})

    return True

#-------------------------------------------------------------------------------
def reset_event(evnt_id=None):
    '''Called via API. Reset the notific_event document, all triggers and
    associated notifics
    '''

    evnt_id = oid(evnt_id)

    g.db.events.update_one(
        {'_id':evnt_id},
        {'$set':{'status':'pending'}})
    n = g.db.notifics.update(
        {'evnt_id': evnt_id},
        {'$set': {
            'tracking.status':'pending',
            'tracking.attempts':0},
         '$unset': {
            'tracking.sid': '',
            'tracking.mid': '',
            'tracking.answered_by': '',
            'tracking.ended_dt': '',
            'tracking.speak': '',
            'tracking.code': '',
            'tracking.duration': '',
            'tracking.error': '',
            'tracking.reason': '',
            'tracking.code': '',
            'tracking.reply': '',
            'tracking.body': '',
            'tracking.sent_dt': '',
            'tracking.error_code': '',
            'tracking.digit': ''}},
        multi=True)
    g.db.triggers.update(
        {'evnt_id': evnt_id},
        {'$set': {'status':'pending'}},
        multi=True)

    log.debug('%s notifics reset', n['nModified'])

#-------------------------------------------------------------------------------
def add(agency, name, event_date, _type):
    '''Creates a new job and adds to DB
    @conf: g.db['groups']['reminders']
    Returns:
      -id (ObjectId)
    '''

    return g.db.events.insert_one({
        'name': name,
        'agency': agency,
        'event_dt': to_utc(d=event_date, t=time(8,0)),
        'type': _type,
        'status': 'pending',
        'opt_outs': 0,
        'trig_ids': []
    }).inserted_id

#-------------------------------------------------------------------------------
def get(evnt_id, local_time=True):

    event = g.db.events.find_one({'_id':evnt_id})
    if local_time == True:
        return to_local(obj=event)
    return event

#-------------------------------------------------------------------------------
def get_list(agency, local_time=True, max=20):
    '''Return list of all events for agency
    '''

    sorted_events = list(g.db.events.find(
        {'agency':agency}).sort('event_dt',-1).limit(max))
    if local_time == True:
        for event in sorted_events:
            event = to_local(obj=event)
    return sorted_events

#-------------------------------------------------------------------------------
def get_triggers(evnt_id, local_time=True, sort_by='type'):

    trigger_list = list(g.db.triggers.find({'evnt_id':evnt_id}).sort(sort_by,1))
    if local_time == True:
        for trigger in trigger_list:
            trigger = to_local(obj=trigger)
    return trigger_list

#-------------------------------------------------------------------------------
def get_notifics(evnt_id, local_time=True, sorted_by='account.event_dt'):

    notific_results = g.db.notifics.aggregate([
        {'$match': {
            'evnt_id': evnt_id
            }},
        {'$lookup': {
            'from': "accounts",
            'localField': "acct_id",
            'foreignField': "_id",
            'as': "account"}},
        {'$group': {
            '_id': '$acct_id',
            'results': { '$push': '$$ROOT'}}}])

    if local_time==True:
        # Convert to list since not possible to rewind aggregate cursors

        notific_list = list(notific_results)

        for notific in notific_list:
            notific = to_local(obj=notific)

        # Returning list
        return notific_list

    # Returning cursor
    return notific_results

#-------------------------------------------------------------------------------
def update_status(evnt_id):
    '''Update event status depending on attached trigger status(es)
    '''

    pend_trigr = g.db.triggers.find(
        {'evnt_id': evnt_id, 'status':'pending'})

    if pend_trigr.count() >= 1:
        status = 'in-progress'
    else:
        status = 'completed'

    g.db.events.update_one(
        {'_id':evnt_id},
        {'$set': {'status':status}})

    log.debug('event updated to %s (evnt_id=%s)', status, str(evnt_id))

#-------------------------------------------------------------------------------
def rmv_notifics(evnt_id, acct_id):

    n_notifics = g.db.notifics.remove({'acct_id':oid(acct_id)})['n']
    n_accounts = g.db.accounts.remove({'_id':oid(acct_id)})['n']
    log.debug('removed %s notifics, %s account for evnt_id="%s"', n_notifics,
    n_accounts, evnt_id)
    return True

#-------------------------------------------------------------------------------
def dump_event(evnt_id):

    event = g.db.events.find_one({'_id':oid(evnt_id)})
    event['triggers'] = get_triggers(event['_id'])

    for trigger in event['triggers']:
        # modifying 'triggers' structure for view rendering
        trigger['count'] = triggers.get_count(trigger['_id'])

    return jsonify(format_bson(event,
        loc_time=True,
        dt_str="%m/%-d/%Y @ %-I:%M%p",
        to_json=True))
