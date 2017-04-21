'''app.main.leaderboard'''
import json, logging
from flask import g
from datetime import datetime, date, timedelta
from app import get_logger, get_keys
from .cal import get_blocks
from .etap import call, get_query, get_udf
log = get_logger('leaderboard')

#-------------------------------------------------------------------------------
def update_accts(query, agcy):

    accts = get_query(query, get_keys('etapestry'))

    for acct in accts:
        g.db.etap_accts.update(
            {'acct_id': acct['id']},
            {'$set': {
                'acct_id': acct['id'],
                'ref': acct['ref'],
                'agcy': agcy,
                'name_format': acct.get('nameFormat'),
                'neighborhood': get_udf('Neighborhood', acct)}},
            upsert=True)

    log.debug('stored %s accts from %s', len(accts), query)

#-------------------------------------------------------------------------------
def update_gifts(accts, agcy):
    '''accts: list of results from db.etap_accts
    '''

    try:
        accts_je_hist = call(
            'get_gift_histories',
            get_keys('etapestry', agcy=agcy),
            data={
                "acct_refs": [x['ref'] for x in accts],
                "start": "01/01/" + str(date.today().year),
                "end": "31/12/" + str(date.today().year)})
    except Exception as e:
        raise

    log.debug('retrieved %s acct je histories', len(accts_je_hist))

    # Each list element contains list of {'amount':<float>, 'date':<str>}

    num_gifts = 0
    total = 0

    for je_hist in accts_je_hist:
        num_gifts += len(je_hist)
        acct_total = 0

        for je in je_hist:
            acct_total += je['amount']
            total += je['amount']

        if len(je_hist) > 0:
            g.db.etap_accts.update_one(
                {'ref':je_hist[0]['ref'], 'agcy':agcy},
                {'$set': {'year':date.today().year, 'ytd': acct_total}})

    log.debug('updated gifts for %s accts', len(accts))

#-------------------------------------------------------------------------------
def get_all_rankings(agcy=None):

    agency = agcy if agcy else g.user.agency

    rankings = g.db.etap_accts.aggregate([
        {'$match': {'agcy':agency}},
        {'$group': {
            '_id': '$neighborhood',
            'ytd': { '$sum': '$ytd'}}},
        {'$sort' : {'ytd':-1}}
    ])

    return rankings

#-------------------------------------------------------------------------------
def get_ranking(neighborhood, agcy=None):

    rankings = get_all_rankings(agcy=agcy if agcy else g.user.agency)

    idx = 0
    for rank in rankings:
        if rank['_id'] == neighborhood:
            count = len(list(rankings)) + idx + 1
            log.debug('%s rank=%s/%s (ytd=$%s)', neighborhood, idx, count, rank['ytd'])
            return
        idx += 1
