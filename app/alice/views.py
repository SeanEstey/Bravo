'''app.alice.views'''

import logging
from flask import request, jsonify, render_template, session
from flask_login import login_required, current_user
from .. import utils, db#, store
from . import alice, helper
from bson.objectid import ObjectId
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    user = db.users.find_one({'user': current_user.username})

    '''
    if not store.__contains__('user'):
    #if user['user'] not in store.keys():
        logger.debug('no user saved in store for %s', user['user'])

        save = {
            'salutation': user['name'],
            'agency': user['agency']
        }

        store.put(user['user'], save)
    else:
        retrieved = store.get(user['user'])
        logger.debug('retrieve user')
        logger.debug(retrieved)
    '''

    return render_template('views/alice.html')

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
@login_required
def get_chatlogs():
    agency = db.users.find_one({'user': current_user.username})['agency']

    chatlogs = helper.get_chatlogs(agency)

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True
        )
    )
