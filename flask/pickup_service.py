

#-------------------------------------------------------------------------------
@celery_app.task
def setup_reminder_jobs():
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    agency = 'vec'
    vec = db['agencies'].find_one({'name':agency})
    conf = vec['reminders']

    today = date.today()
    block_date = today + timedelta(days=conf['days_in_advance_to_schedule'])

    for cal_id in vec['cal_ids']:
        blocks += get_blocks(
          vec['cal_ids'][cal_id],
          datetime.combine(block_date,time(8,0)),
          datetime.combine(block_date,time(9,0)),
          vec['google']['oauth'])

    try:
        # Load reminder schema
        with open('templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)['reminders']
    except Exception as e:
        logger.error(str(e))

    schema = schemas[0] # TODO: Fixme

    for block in blocks:
        try:
            accounts = etap.call(
              'get_query_accounts',
              vec['etapestry'],
              {'query':block, 'query_category':vec['etapestry']['query_category']}
            )
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if len(accounts) < 1:
            continue

        event = add_reminder_event(agency, block, block_date)

        # Create reminders
        for account in accounts:
            npu = etap.get_udf('Next Pickup Date', account).split('/')

            if len(npu) < 3:
                logger.error('Account %s missing npu. Skipping.', account['id'])

                # Use the event_date as next pickup
                pickup_dt = event_dt
            else:
                npu = npu[1] + '/' + npu[0] + '/' + npu[2]
                pickup_dt = local.localize(parse(npu + " T08:00:00"), is_dst=True)

            for trigger in event['triggers']:
                add_notification(agency, account, block_date, trigger['type']
                        trigger['_id'] schema):

        add_future_pickups(str(event['_id']))

    #logger.info(
    #  'Created reminder job for Blocks %s. Emails fire at %s, calls fire at %s',
    #  str(blocks), job['email']['fire_dt'].isoformat(),
    #  job['voice']['fire_dt'].isoformat())

    return True

#-------------------------------------------------------------------------------
def add_reminder_event(agency, block, date):
    '''Creates event_reminder document as well as triggers'''

    conf = db['agencies'].find_one({'name':agency})['reminders']

    phone_trig = add_trigger(agency, block_d, 'phone', conf['phone'],
                               mediums=['sms', 'voice'])
    email_trig = add_trigger(agency, block_d, 'email', conf['email'])}

    schema = {
        'name': schema['name'],
        'type': schema['type'],
        'email': {
            'no_pickup': schema['no_pickup']
        }
    }

    return reminders.add_event(agency, block, date, [phone_trig, email_trig], schema)

#-------------------------------------------------------------------------------
def add_notification(agency, account, block_d, _type, trig_id, schema):
    '''Adds an event reminder for given job
    Can contain 1-3 reminder objects: 'sms', 'voice', 'email'
    Returns:
      -True on success, False otherwise'''

    sms_enabled = False

    udf = {
        "status": etap.get_udf('Status', account),
        "office_notes": etap.get_udf('Office Notes', account),
        "block": etap.get_udf('Block', account),
        "future_pickup_dt": None
    }

    if _type == 'phone':
        if not etap.get_phone(account):
            return False

        conf = {
            'to': etap.get_primary_phone(account),
            'source': 'template'
            'template' = schema['voice']['reminder']['file']
        }

        reminders.add_notification(
            agency, 'voice', account, trig_id, udf, conf
        )
    elif _type == 'email':
        if not account.get('email'):
            return False

        conf = {
            "recipient": account['email'],
            "template": schema['email']['reminder']['file'],
            "subject": schema['email']['reminder']['subject']
        }

        reminders.add_notification(
            agency, 'email', account, trig_id, udf, conf)

    return True
