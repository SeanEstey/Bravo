# app.main.donors

import json, logging, math, re
from datetime import date, timedelta, datetime
from dateutil.parser import parse
from flask import g, request
from app import get_keys
from app.lib import html, mailgun
from app.lib.timer import Timer
from app.lib.dt import ddmmyyyy_to_date as to_date
from app.main.etapestry import EtapError, to_datetime, mod_acct, get_acct, get_udf, call
from app.main.maps import geocode
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get(aid, ref=None, sync_ytd_gifts=False):

    if sync_ytd_gifts and ref:
        from app.main.tasks import _get_gifts
        now = date.today()
        rv = _get_gifts.delay(ref, date(now.year,1,1), date(now.year,12,31))

    return get_acct(aid)

#-------------------------------------------------------------------------------
def get_matches(query):
    """Find cache matches for query string. Checks indexed fields.
    """

    matches = g.db['cachedAccounts'].find({
      'group':g.group,
      '$or': [
         {'account.name':{'$regex':query}},
         {'account.email':{'$regex':query}}
      ]
    }).limit(10)

    print 'Query str="%s", matches=%s' % (query, matches.count())

    return list(matches)

#-------------------------------------------------------------------------------
def gift_history(ref):

    documents = g.db['cachedGifts'].find(
        {'group':g.group, 'gift.accountRef':str(ref), 'gift.type':5}
    ).sort('gift.date',-1)
    return [doc['gift'] for doc in documents]

#-------------------------------------------------------------------------------
def update_geolocation(account):
    """Store geolocation if not present and update on address change.
    """

    # TODO: Test if personaLastModifiedDate is instanceof datetime

    document = g.db['cachedAccounts'].find_one(
        {'group':g.group, 'account.id':account['id']})

    update = False

    if not document.get('geolocation'):
        update = True
    else:
        geo_addr = document['geolocation'].get('acct_address')
        if geo_addr != account['address']:
            log.debug('Address change. Geo addr=%s, Acct addr=%s',
                geo_addr, account['address'])
            update = True

    if not update:
        return

    faddr = ", ".join([account.get('address',''), account.get('city',''), account.get('state','')])

    try:
        geolocation = geocode(faddr, get_keys('google')['geocode']['api_key'])[0]
    except Exception as e:
        log.exception('Failed to geolocate Account #%s at "%s".', account['id'], account['address'])
        geolocation = {'Desc':'Geolocation not found for %s.' % account['address']}
    else:
        geolocation['acct_address'] = account.get('address')

        g.db['cachedAccounts'].update_one(
          {'group':g.group, 'account.id':account['id']},
          {'$set': {'group':g.group, 'account':to_datetime(account), 'geolocation':geolocation}},
          upsert=True)

        log.debug('Geolocated Acct #%s', account['id'])

        return geolocation

#-------------------------------------------------------------------------------
def get_location(acct_id=None, cache=True):

    if not acct_id or not re.search(r'\d{1,7}', acct_id):
        raise Exception('Invalid Account.id "%s" for acquiring location.', acct_id)

    document = g.db['cachedAccounts'].find_one({'group':g.group,'account.id':int(acct_id)})

    if document and document.get('geolocation'):
        return document['geolocation']

    if document and document.get('account'):
        acct = document['account']
    else:
        acct = get_acct(acct_id, cached=False)

    return update_geolocation(acct)

#-------------------------------------------------------------------------------
def get_next_pickup(email):

    try:
        return call('get_next_pickup', data={'email':email})
    except EtapError as e:
        return e.message

#-------------------------------------------------------------------------------
def ytd_gifts(ref, year):

    jan_1 = datetime(year,1,1)
    dec_31 = datetime(year,12,31)

    gifts = g.db['cachedGifts'].find({
        'group':g.group,
        'gift.accountRef':ref,
        'gift.date': {'$gte':jan_1, '$lte':dec_31}
    })

    log.debug('Retrieved %s cached Gifts', gifts.count())
    return list(gifts)

#-------------------------------------------------------------------------------
def save_rfu(acct_id, body, date=False, ref=False, fields=False):
    '''Add or update RFU Journal Note for acct, update any necessary User
    Defined Fields
    '''

    func = 'update_note' if ref else 'add_note'
    data = {
        "ref": ref,
        "acct_id": acct_id,
        "body": body,
        "date": date}

    try:
        note_rv = call(func, data=data)
    except Exception as e:
        raise

    if fields:
        try:
            updt_rv = call(
                'modify_acct',
                data={
                    'acct_id':acct_id,
                    'persona': [],
                    'udf':json.loads(fields)})
        except Exception as e:
            raise

    log.debug('Created issue in Bravo Sheets', extra={'fields':note_rv})

    return note_rv

#-------------------------------------------------------------------------------
def create_accts(accts):
    '''Called from API. g.user is set'''

    log.warning('Creating %s accounts...', len(json.loads(accts)))

    try:
        rv = call('add_accts', data={'accts':accts})
    except Exception as e:
        log.error('add_accts. desc=%s', str(e))
        log.debug(str(e))

    log.warning('%s', rv['description'])

    if len(rv['errors']) > 0:
        log.error(rv['errors'])

#-------------------------------------------------------------------------------
def is_inactive(acct, days=270):

    drop_date = get_udf('Dropoff Date', acct)

    # Set Dropoff Date == acct creation date if empty

    if not drop_date:
        log.debug('accountCreatedDate=%s', acct['accountCreatedDate'])
        return

    # Must have been dropped off > @days

    delta = date.today() - to_date(drop_date)

    if delta.days < days:
        return False

    cutoff_date = date.today() - timedelta(days=days)

    # Retrieve journal entries from cutoff, see if donations made in period

    try:
        gifts = call(
            'get_gifts',
            data={
                "ref": acct['ref'],
                "startDate": cutoff_date.strftime('%d/%m/%Y'),
                "endDate": date.today().strftime('%d/%m/%Y')
            },
            cache=True
        )
    except EtapError as e:
        log.exception('Failed to retrieve gifts for Account #%s.', acct['id'])
        raise

    if len(gifts) > 0:
        return False
    else:
        log.debug('Inactive donor: Account #%s', acct['id'])
        return True

#-------------------------------------------------------------------------------
def unsubscribe(group):
    if not request.args.get('email'):
        raise Exception('no email included in unsub')

    g.group = group
    log.debug('unsub email=%s', request.args['email'])
    conf = get_keys('mailgun')

    try:
        mailgun.send(
            conf['from'],
            'Unsubscribe Request',
            '%s has requested email unsubscription. Please contact to see if '\
            'they want to cancel the service.' % request.args['email'],
            conf,
            v={'type':'unsub'})
    except Exception as e:
        log.error(str(e))
        log.debug(str(e))
        return 'failed'

    return "We've received your request. "\
        "Please give us a few days to remove your email from our correspondence"
