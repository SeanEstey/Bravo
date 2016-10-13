'''notify.email'''

'''{
    (...),
    "on_send" : {
        "source" : "template",
        "path" : "voice/vec/reminder.html"
    },
    "on_reply": {
        "module": "pickup_service",
        "func": "on_call_interact"
    },
    "tracking": {
        "attempts": 0,
        "duration": 13,
        "
        "ended_dt": "ISODate(...)",
        "sid": "49959jfd93jd"
    },
    "to" : "foo@bar.com",
    "type" : "email"
}'''


#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    template = notific['on_send']['template'][key]

    with current_app.test_request_context():
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            body = render_template(
                template['file'],
                to = notific['to'],
                account = utils.mongo_formatter(
                    db['accounts'].find_one({'_id':notific['acct_id']}),
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True
                ),
                evnt_id = notific['evnt_id']
            )
        except Exception as e:
            logger.error('render email: %s ', str(e))
            current_app.config['SERVER_NAME'] = None
            return False
        current_app.config['SERVER_NAME'] = None

    mid = mailgun.send(
        notific['to'],
        template['subject'],
        body,
        mailgun_conf)

    if mid == False:
        status = 'failed'
    else:
        status = 'queued'

    agency = db['agencies'].find_one({'mailgun.domain': mailgun_conf['domain']})

    db['emails'].insert({
        'agency': agency['name'],
        'mid': mid,
        'status': status,
        'type': 'notification',
        'on_status': {}
    })

    db['notifics'].update_one(
        {'_id':notific['_id']},
        {'$set': {'status':status, 'mid': mid}})

    return mid

#-------------------------------------------------------------------------------
def on_email_status(webhook):
    '''
    @webhook: webhook args POST'd by mailgun'''

    db['notifics'].update_one(
      {'mid': webhook['Message-Id']},
      {'$set':{
        "status": webhook['event'],
        "code": webhook.get('code'),
        "reason": webhook.get('reason'),
        "error": webhook.get('error')
      }}
    )
