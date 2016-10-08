
#-------------------------------------------------------------------------------
def find(agency, accounts):
    '''Analyze list of eTap account objects for non-participants
    which is an active account with no > $0 gifts in past X days where X is
    set by db['agency']['config']['non-participant days']
    Output: list of np's, empty list if none found
    '''

    # Build list of accounts to query gift_histories for
    viable_accounts = []

    agency_settings = db['agencies'].find_one({'name':agency})

    etap_id = agency_settings['etapestry']

    keys = {'user':etap_id['user'], 'pw':etap_id['pw'],
            'agency':agency,'endpoint':app.config['ETAPESTRY_ENDPOINT']}

    for account in accounts:
        # Test if Dropoff Date was at least 12 months ago
        d = etap.get_udf('Dropoff Date', account).split('/')

        if len(d) < 3:
            date_str = parse(account['accountCreatedDate']).strftime("%d/%m/%Y")

            d = date_str.split('/')

            # If missing Signup Date or Dropoff Date, use 'accountCreatedDate'
            try:
                etap.call('modify_account', keys, {
                  'id': account['id'],
                  'udf': {
                    'Dropoff Date': date_str,
                    'Signup Date': date_str
                  },
                  'persona': []
                })
            except Exception as e:
                logger.error('Error modifying account %s: %s', account['id'], str(e))
                continue

        dropoff_date = datetime(int(d[2]), int(d[1]), int(d[0]))
        now = datetime.now()
        time_active = now - dropoff_date

        # Account must have been active for >= non_participant_days
        if time_active.days >= agency_settings['config']['non_participant_days']:
            viable_accounts.append(account)

    logger.info('found %s older accounts', str(len(viable_accounts)))

    if len(viable_accounts) == 0:
        return []

    np_cutoff = now - timedelta(days=agency_settings['config']['non_participant_days'])

    logger.info('Non-participant cutoff date is %s', np_cutoff.strftime('%b %d %Y'))

    try:
        # Retrieve non-zero gift donations from non-participant cutoff date to
        # present
        gift_histories = etap.call('get_gift_histories', keys, {
          "account_refs": [i['ref'] for i in viable_accounts],
          "start_date": str(np_cutoff.day) + "/" + str(np_cutoff.month) + "/" +str(np_cutoff.year),
          "end_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year)
        })
    except Exception as e:
        logger.error('Failed to get gift_histories', exc_info=True)
        return str(e)

    now = datetime.now()

    nps = []

    for idx, gift_history in enumerate(gift_histories):
        if len(gift_history) == 0:
            nps.append(viable_accounts[idx])

    logger.info('Found %d non-participants', len(nps))

    return nps
