# app.main.account

"""eTapestry Account representation.
"""

from flask import g
from datetime import datetime
from dateutil.parser import parse
from app.lib.timer import Timer
from app.main.etapestry import call


UDF = {
    'displayType': {
        'Text': 0,
        'Single Select': 1,
        'Multi Select': 2,
        'Text Area': 3
    },
    'dataType': {
        'Text': 0,
        'Date': 1,
        'Month/Day': 2,
        'Number': 3,
        'Currency': 4
    }
}

DATE_FIELDS = [
    'accountCreatedDate',
    'accountLastModifiedDate',
    'personaLastModifiedDate',
    'personaCreatedDate'
]

#-------------------------------------------------------------------------------
class Account(object):

    account = None
    entries = None

    #-------------------------------------------------------------------------------
    def _cache(self, force_insert=False):

        if force_insert:
            print 'Caching Account'
            g.db['cachedAccounts'].insert_one({'group':g.group, 'account':self.account})
            return

        doc = g.db['cachedAccounts'].find_one({'group':g.group,'account.id':self.account['id']})

        if not doc:
            print 'Caching Account'
            g.db['cachedAccounts'].insert_one({'group':g.group,'account':self.account})
            return
        else:
            for f in DATE_FIELDS:
                if doc['account'].get(f) != self.account.get(f):
                    g.db['cachedAccounts'].update_one(
                        {'_id':doc['_id']},
                        {'$set':{'account':self.account}})
                    print 'cachedAccount updated'
                    return

            print 'cachedAccount is current'

    #-------------------------------------------------------------------------------
    def _load(self, aid=None, ref=None, from_cache=True, to_cache=True):

        timer = Timer()
        acct = None
        doc = None
        cache_checked = False
        force_insert = False
        from_etap = True if not from_cache else False

        # Check from Cache
        if from_cache:
            params = {'group':g.group,'account.id':aid} if aid else {'group':g.group,'account.ref':str(ref)}
            doc = g.db['cachedAccounts'].find_one(params)

            if not doc:
                force_insert = True
                print 'No cache. Pulling from eTapestry'
            else:
                print 'Returning cached Account'
                self.account = doc['account']
                return

        if force_insert:
            print 'Cache empty. Pulling from eTapestry'
        else:
            print 'Pulling Account from eTapestry w/o checking cache'

        acct = call('get_account', data={'acct_id':int(aid)}) if aid else call('get_account', data={'ref':ref})

        if not acct:
            raise Exception('Account not found, aid=%s, ref=%s.' % (aid, ref))

        # Convert all date strings to datetime

        for f in DATE_FIELDS:
            if acct.get(f) and type(acct[f]) in [str, unicode]:
                acct[f] = parse(acct[f])

        for f in acct['accountDefinedValues']:
            if f['dataType'] != UDF['dataType']['Date'] or isinstance(f['value'], datetime):
                continue

            parts = f['value'].split('/')
            f['value'] = datetime(int(parts[2]), int(parts[1]), int(parts[0]))

        self.account = acct

        if to_cache:
            self._cache(force_insert=force_insert)

    #---------------------------------------------------------------
    def get(self, field):

        # Account property
        if self.account.get(field):
            return self.account.get(field)

        # DefinedValue property
        values = []
        value = None
        for f in self.account['accountDefinedValues']:
            if f['fieldName'] != field:
                continue

            value = f['value']

            if f['displayType'] == UDF['displayType']['Multi Select']:
                values.append(value)
            else:
                return value

        return values if len(values) > 0 else None

    #---------------------------------------------------------------
    def set(self, field, value):
        """Update Account property
        """

        if type(value) is list:
            # Update UDF Multi Select
            print 'Cannot update UDF Multi-Select field'
            return

        if self.account.get(field):
            self.account[field] = value
            return

        for f in self.account['accountDefinedValues']:
            if f['fieldName'] != field:
                continue
            f['value'] = value

    #---------------------------------------------------------------
    def toEtapJSON(self):
        '''Convert all datetimes to native etapestry "dd/mm/yyyy" strings,
        serialize to JSON
        '''
        pass

    #---------------------------------------------------------------
    def toPyObj(self):
        '''Convert all eTapestry str dates ("dd/mm/yyyy") to datetime in dict
        '''
        pass

    #---------------------------------------------------------------
    def __init__(self, acct=None, aid=None, from_cache=True, to_cache=True):

        if acct:
            self.account = acct
        elif aid:
            self._load(aid=aid, from_cache=from_cache, to_cache=to_cache)





#---------------------------------------------------------------
#def __getattr__(self, attr):
#    """Access obj properties and UDF's through dict notation
#    i.e. blocks = acct['Block']
#    """
#    print 'get attr %s' % attr
#    #print self.__dict__
#    return self.account[attr]
