'''app.main.accounts'''
import logging
from flask import g
from .. import get_keys, etap
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get(acct_id):
    return etap.call(
        'get_account',
        get_keys('etapestry'),
        data={'account_number': int(acct_id)})
