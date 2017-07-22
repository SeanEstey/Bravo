# app.main.donors

import json, logging, math, re
from datetime import date, timedelta, datetime
from dateutil.parser import parse
from flask import g, request
from app import get_keys
from app.lib import html, mailgun
from app.lib.timer import Timer
from app.lib.dt import ddmmyyyy_to_date as to_date
from app.main.etapestry import EtapError, mod_acct, get_acct, get_udf, call
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
def get_summary_stats(ref):

    t = Timer()

    gifts = call(
        'get_journal_entries',
        data={'ref':ref,'startDate':'01/01/2001', 'endDate':'18/07/2017','types':[5]},
        cache=True)

    # 'date' will be in dd/mm/yyyy format
    rv = []
    for gift in gifts:
        rv.append({
            'date': gift['date'],
            'amount': gift['amount']
        })

    log.debug('Queried %s gifts [%s]', len(gifts), t.clock(t='ms'))

    # Can handle empty journal history result???

    return rv

    """
    gifts = g.db['cachedGifts'].find({'gift.accountRef':str(ref)})

    total = 0
    n_gifts = 0


    if n_gifts > 0:
        avg = total/n_gifts
    else:
        avg = 0

    log.debug('%s gifts cached for ref=%s. total=%s.', n_gifts, ref, total)

    return {'total':total, 'average':avg, 'n_gifts':n_gifts}
    """

#-------------------------------------------------------------------------------
def get_location(acct_id=None):

    if not acct_id or not re.search(r'\d{1,7}', acct_id):
        raise Exception('Invalid Account.id "%s" for acquiring location.', acct_id)

    cached_doc = g.db['cachedAccounts'].find_one({'group':g.group,'account.id':int(acct_id)})

    if cached_doc:
        if cached_doc.get('geolocation'):
            log.debug('Returning geolocation of cached account.')
            return cached_doc['geolocation']
        else:
            acct = cached_doc['account']
    else:
        # Pull Account from etapestry (will raise Exception if ID invalid)
        acct = get_acct(acct_id, cached=False)

    # We have Account (cached or otherwise) but missing geolocation.
    # Acquire it, cache it, return it.

    try:
        geolocation = geocode(
            ", ".join([acct.get('address',''), acct.get('city',''), acct.get('state','')]),
            get_keys('google')['geocode']['api_key']
        )[0]
    except Exception as e:
        log.exception('Failed to geolocate Account #%s at "%s".', acct_id, acct['address'])
        raise
    else:
        from app.main.etapestry import to_datetime

        # Cache it.
        g.db['cachedAccounts'].update_one(
          {'group':g.group, 'account.id':acct['id']},
          {'$set': {'group':g.group, 'account':to_datetime(acct), 'geolocation':geolocation}},
          upsert=True)

        log.debug('Geolocated and cached account.')
        return geolocation

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
