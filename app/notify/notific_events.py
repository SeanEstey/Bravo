import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from werkzeug import secure_filename
import codecs
from bson.objectid import ObjectId
from flask.ext.login import current_user
import csv
import os

# Import bravo modules
from app import utils

# Import objects
from app import app, db, socketio

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def add(agency, name, event_date):
    '''Creates a new job and adds to DB
    @conf: db.agencies->'reminders'
    Returns:
      -id (ObjectId)
    '''

    return db['notification_events'].insert_one({
        'name': name,
        'agency': agency,
        'event_dt': utils.naive_to_local(datetime.combine(event_date, time(8,0))),
        'status': 'pending',
        'opt_outs': 0,
        'triggers': []
    }).inserted_id


#-------------------------------------------------------------------------------
def get_triggers(event_id):
    return db['triggers'].find({'event_id':event_id})

#-------------------------------------------------------------------------------
def get_grouped_notifications(event_id):
    return db['notifications'].aggregate([
        {'$match': {
            'event_id': event_id
            }
        },
        {'$group': {
            '_id': '$account.id',
            'results': { '$push': '$$ROOT'}
        }}
    ])


#-------------------------------------------------------------------------------
def reset(event_id):
    '''Reset the notification_event document, all triggers and associated
    notifications'''

    event_id = ObjectId(event_id)

    db['notification_events'].update_one(
        {'_id':event_id},
        {'$set':{'status':'pending'}}
    )

    n = db['notifications'].update(
        {'event_id': event_id}, {
            '$set': {
                'status': 'pending',
                'attempts': 0,
            },
            '$unset': {
                'account.udf.opted_out': '',
                'sid': '',
                'answered_by': '',
                'ended_at': '',
                'speak': '',
                'code': '',
                'duration': '',
                'error': '',
                'reason': '',
                'code': ''
            }
        },
        multi=True
    )

    db['triggers'].update(
        {'event_id': event_id},
        {'$set': {'status':'pending'}},
        multi=True
    )

    logger.info('%s notifications reset', n['nModified'])

#-------------------------------------------------------------------------------
def remove(event_id):
    # remove all triggers, notifications, and event
    event_id = ObjectId(event_id)

    n_notific = db['notifications'].remove({'event_id':event_id})

    n_triggers = db['triggers'].remove({'event_id': event_id})

    db['notification_events'].remove({'_id': event_id})

    logger.info('Removed %s notifications and %s triggers', n_notific, n_triggers)

    return True

#-------------------------------------------------------------------------------
def get_list(agency, max=10):
    '''Display jobs for agency associated with current_user
    If no 'n' specified, display records (sorted by date) {1 .. JOBS_PER_PAGE}
    If 'n' arg, display records {n .. n+JOBS_PER_PAGE}
    Returns: list of notification_event dict objects
    '''

    agency = db['users'].find_one({'user': current_user.username})['agency']

    events = db['notification_events'].find({'agency':agency})

    if events:
        events = events.sort('event_dt',-1).limit(app.config['JOBS_PER_PAGE'])

    # Convert from cursor->list so re-iterable
    events = list(events)

    for event in events:
        event['event_dt'] = utils.utc_to_local(event['event_dt'])

    '''
    for job in jobs:
        if 'voice' in job:
            job['voice']['fire_dt'] = job['voice']['fire_dt'].replace(tzinfo=pytz.utc).astimezone(local)

        if 'email' in job:
            job['email']['fire_dt'] = job['email']['fire_dt'].replace(tzinfo=pytz.utc).astimezone(local)

        if 'event_dt' in job:
            job['event_dt'] = job['event_dt'].replace(tzinfo=pytz.utc).astimezone(local)
    '''

    return events

#-------------------------------------------------------------------------------
def get_notifications(event_id):
    notific_list = db['notifications'].find({'event_id':event_id})

    # TODO: Group them by account['id']
    return notific_list


#-------------------------------------------------------------------------------
def parse_csv(csvfile, import_fields):
    '''Checks the .csv file buffer for correct headers/rows
    csvfile: buffer from opened .csv file
    returns: buffer of rows on success, error str on failure
    import_fields: list of header column mappings from json schema
    '''

    reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
    buffer = []
    header_err = False

    try:
        for row in reader:
            # Test header row
            if reader.line_num == 1:
                if len(row) != len(import_fields):
                    header_err = True
                else:
                    for col in range(0, len(row)):
                      if row[col] != import_fields[col]['file_header']:
                          header_err = True
                          break

                if header_err:
                    columns = []
                    for element in import_fields:
                        columns.append(element['file_header'])

                    logger.error('Invalid header row. Missing columns: %s', str(columns))

                    return 'Your file is missing the proper header rows:<br> \
                    <b>' + str(columns) + '</b><br><br>' \
                    'Here is your header row:<br><b>' + str(row) + '</b><br><br>' \
                    'Please fix your mess and try again.'

            # Skip over empty Row 2 in eTapestry export files
            elif reader.line_num == 2:
                continue
            # Read each line from file into buffer
            else:
                if len(row) != len(import_fields):
                    return 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
                    ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
                else:
                    buffer.append(row)
    except Exception as e:
        logger.error('reminders.parse_csv: %s', str(e))
        return False

    return buffer

#-------------------------------------------------------------------------------
def submit_from(form, file):
    '''POST request to create new job from new_job.html template'''

    # TODO: Add event_date field to form.

    # TODO: Add timezone info to datetimes before inserting into mongodb

    logger.debug('new job form: %s', str(form))

    # A. Validate file
    try:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
        else:
            logger.error('could not save file')

            return {'status':'error',
                    'title': 'Filename Problem',
                    'msg':'Could not save file'}
    except Exception as e:
        logger.error(str(e))

        return {
          'status':'error',
          'title':'file problem',
          'msg':'could not upload file'
        }

    agency = db['users'].find_one({'user': current_user.username})['agency']

    # B. Get schema definitions from json file
    try:
        with open('app/templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)['reminders']
    except Exception as e:
        logger.error(str(e))
        return {'status':'error',
                'title': 'Problem Reading reminder_templates.json File',
                'msg':'Could not parse file: ' + str(e)}

    schema = ''
    for s in schemas:
        if s['name'] == form['template_name']:
            schema = s
            break

    # C. Open and parse submitted .CSV file
    try:
        with codecs.open(file_path, 'r', 'utf-8-sig') as f:
            buffer = parse_csv(f, schema['import_fields'])

            if type(buffer) == str:
                return {
                  'status':'error',
                  'title': 'Problem Reading File',
                  'msg':buffer
                }

            logger.info('Parsed %d rows from %s', len(buffer), filename)
    except Exception as e:
        logger.error('submit_job: parse_csv: %s', str(e))

        return {'status':'error',
                'title': 'Problem Reading File',
                'msg':'Could not parse .CSV file: ' + str(e)}

    if not form['job_name']:
        job_name = filename.split('.')[0].replace('_',' ')
    else:
        job_name = form['job_name']

    try:
        fire_calls_dtime = parse(form['date'] + ' ' + form['time'])
    except Exception as e:
        logger.error(str(e))

        return {
          'status':'error',
          'title': 'Invalid Date',
          'msg':'Could not parse the schedule date you entered: ' + str(e)
        }

    #local = pytz.timezone("Canada/Mountain")
    #event_dt = local.localize(datetime.combine(block_date, time(8,0)), is_dst=True)

    # D. Create mongo 'job' and 'reminder' records
    job = {
        'name': job_name,
        'agency': agency,
        'schema': schema,
        #'event_dt':
        'voice': {
            'fire_dt': fire_calls_dtime,
            'count': len(buffer)
        },
        'status': 'pending'
    }

    # Special cases
    if form['template_name'] == 'announce_voice':
        job['audio_url'] = form['audio-url']
    elif form['template_name'] == 'announce_text':
        job['message'] = form['message']

    #logger.debug('new job dump: %s', json.dumps(job))

    job_id = db['jobs'].insert(job)
    job['_id'] = job_id

    try:
        errors = []
        reminders = []

        for idx, row in enumerate(buffer):
            msg = create(job, schema, idx, row, errors)

            if msg:
                reminders.append(msg)

            if len(errors) > 0:
                e = 'The file <b>' + filename + '</b> has some errors:<br><br>'
                for error in errors:
                    e += error
                    db['jobs'].remove({'_id':job_id})

                return {'status':'error', 'title':'File Format Problem', 'msg':e}

        db['reminders'].insert(reminders)

        logger.info('[%s] Job "%s" Created [ID %s]', agency, job_name, str(job_id))

        # Special case
        #if form['template_name'] == 'etw':
        get_next_pickups.apply_async((str(job['_id']), ), queue=app.config['DB'])

        banner_msg = 'Job \'' + job_name + '\' successfully created! '\
                + str(len(reminders)) + ' messages imported.'

        return {'status':'success', 'msg':banner_msg}

    except Exception as e:
        logger.error(str(e))

        return {'status':'error', 'title':'error', 'msg':str(e)}

#-------------------------------------------------------------------------------
def _print(event_id):
    if isinstance(event_id, str):
        event_id = ObjectId(event_id)

    job = db['notification_events'].find_one({'_id':event_id})

    if 'ended_at' in job:
        time_elapsed = (job['voice']['ended_at'] - job['voice']['started_at']).total_seconds()
    else:
        time_elapsed = ''

    summary = {
        "totals": {
          "completed": {
            'answered': db['reminders'].find(
                {'job_id':job_id, 'voice.answered_by':'human'}).count(),
            'voicemail': db['reminders'].find(
                {'job_id':job_id, 'voice.answered_by':'machine'}).count()
          },
          "no-answer" : db['reminders'].find(
              {'job_id':job_id, 'voice.status':'no-answer'}).count(),
          "busy": db['reminders'].find(
              {'job_id':job_id, 'voice.status':'busy'}).count(),
          "failed" : db['reminders'].find(
              {'job_id':job_id, 'voice.status':'failed'}).count(),
          "time_elapsed": time_elapsed
        },
        "calls": list(db['reminders'].find(
            {'job_id':job_id},{'voice.ended_at':0, 'job_id':0}))
    }

    return summary

#-------------------------------------------------------------------------------
def email_summary(event_id):
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)

    job = db['jobs'].find_one({'_id':job_id})

    try:
        r = requests.post(app.config['LOCAL_URL'] + '/email/send', data=json.dumps({
          "recipient": app.config['FROM_EMAIL'],
          "template": 'email/job_summary.html',
          "subject": 'Job Summary %s' % job['name'],
          "data": {
            "summary": {
              "answered": db['reminders'].find({
                'job_id':job_id, 'voice.answered_by':'human'}).count(),
              "voicemail": db['reminders'].find({
                'job_id':job_id, 'voice.answered_by':'machine'}).count(),
              "no_answer" : db['reminders'].find({
                'job_id':job_id, 'voice.status':'no-answer'}).count(),
              "busy": db['reminders'].find({
                'job_id':job_id, 'voice.status':'busy'}).count(),
              "failed" : db['reminders'].find({
                'job_id':job_id, 'voice.status':'failed'}).count()
            },
            "fails": db['reminders'].find(
              {'job_id':job_id,
               '$or': [
                 {"email.status" : "bounced"},
                 {"email.status" : "dropped"},
                 {"voice.status" : "failed"}
               ]
              },
              {'custom': 1, 'email.error': 1, 'voice.error':1,
               'voice.code':1, 'email.status': 1, '_id': 0})
          }
        }))

        logger.info('Email report sent')
    except Exception as e:
        logger.error('Error sending job_summary email: %s', str(e))
