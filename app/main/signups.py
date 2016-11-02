'''app.main.signups'''

import logging
from flask import request, current_app
from datetime import date

from .. import gsheets
from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def on_email_delivered():
    '''Mailgun webhook called from view. Has request context'''

    logger.info('signup welcome delivered to %s', request.form['recipient'])

    email = db['emails'].find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    gsheets.update_entry(
      email['agency'],
      request.form['event'],
      email['on_status']['update']
    )

#-------------------------------------------------------------------------------
def on_email_dropped():
    msg = 'signup welcome to %s dropped. %s.' %(
        request.form['recipient'], request.form['reason'])

    logger.info(msg)

    email = db['emails'].find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    gsheets.update_entry(
      email['agency'],
      request.form['event'],
      email['on_status']['update']
    )

    from .. import tasks
    tasks.rfu.apply_async(
        args=[
            email['agency'],
            msg + request.form.get('description')],
        kwargs={'_date': date.today().strftime('%-m/%-d/%Y')},
        queue=current_app.config['DB']
    )
