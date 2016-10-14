'''app.main.signups'''

#-------------------------------------------------------------------------------
def on_email_delivered(email, webhook):
    '''Forwarded Mailgun webhook on receipt email event.
    Update Sheets accordingly'''

    # DOES FLASK CONTEXT STILL EXIST HERE?? CALLED FROM INSIDE VIEW

    logger.info('Email to %s %s <welcome>',
      webhook['recipient'],
      webhook['event'])

    db['emails'].update_one(
      {'mid': webhook['Message-Id']},
      {'$set': {'status':webhook['event']}})

    try:
        gsheets.update_entry(
          email['agency'],
          webhook['event'],
          email['on_status']['update']
        )
    except Exception as e:
        logger.error("Error writing to Google Sheets: " + str(e))
        return 'Failed'
