'''app.main.leaderboard'''
import json
from flask import g
from datetime import datetime, date, timedelta
from app import get_keys
from .cal import get_blocks
from .etap import call, get_query, get_udf
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def update_accts(query):

    accts = get_query(query)

    for acct in accts:
        g.db['accts_cache'].update(
            {'group':g.group, 'account.id': acct['id']},
            {'$set': {
                'acct_id': acct['id'],
                'ref': acct['ref'],
                'group': g.group,
                'name_format': acct.get('nameFormat'),
                'neighborhood': get_udf('Neighborhood', acct)}},
            upsert=True)

    log.debug('stored %s accts from %s', len(accts), query)

#-------------------------------------------------------------------------------
def update_gifts(accts):
    '''accts: list of results from db.etap_accts
    '''

    for acct in accts:
        try:
            accts_je_hist = call(
                'get_gifts',
                data={
                    "ref": acct['ref'],
                    "startDate": "01/01/" + str(date.today().year),
                    "endDate": "31/12/" + str(date.today().year)})
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
            g.db['accts_cache'].update_one(
                {'ref':je_hist[0]['ref'], 'group':g.group},
                {'$set': {'year':date.today().year, 'ytd': acct_total}})

    log.debug('updated gifts for %s accts', len(accts))

#-------------------------------------------------------------------------------
def get_all_rankings(group=None):

    g.group = group if group else g.group

    rankings = g.db['accts_cache'].aggregate([
        {'$match': {'group':g.group}},
        {'$group': {
            '_id': '$neighborhood',
            'ytd': { '$sum': '$ytd'}}},
        {'$sort' : {'ytd':-1}}
    ])

    return rankings

#-------------------------------------------------------------------------------
def get_ranking(neighborhood, group=None):

    rankings = get_all_rankings(group=group if group else g.group)

    idx = 0
    for rank in rankings:
        if rank['_id'] == neighborhood:
            count = len(list(rankings)) + idx + 1
            log.debug('%s rank=%s/%s (ytd=$%s)', neighborhood, idx, count, rank['ytd'])
            return
        idx += 1
