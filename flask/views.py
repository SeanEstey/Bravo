import json
import flask
from flask import Flask,request,g,Response,url_for
from flask.ext.login import login_user, logout_user, current_user, login_required

import app
from app import app, db, logger, login_manager
import reminders
import auth
from config import *

@app.before_request
def before_request():
  g.user = current_user

@login_manager.user_loader
def load_user(username):
  return auth.load_user(username)

@app.route('/login', methods=['GET','POST'])
def login():
  return auth.login()

@app.route('/logout', methods=['GET'])
def logout():
  logout_user()
  logger.info('User logged out')
  return flask.redirect(PUB_URL)

@app.route('/', methods=['GET'])
@login_required
def index():
  return reminders.view_main()

@app.route('/log')
@login_required
def view_log():
  n = 50
  size = os.path.getsize(LOG_FILE)

  with open(LOG_FILE, "rb") as f:
    fm = mmap.mmap(f.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
    try:
      for i in xrange(size - 1, -1, -1):
        if fm[i] == '\n':
          n -= 1
          if n == -1:
            break
        lines = fm[i + 1 if i else 0:].splitlines()
    except Exception, e:
      logger.error('/log: %s', str(e))
    finally:
      fm.close()

  return flask.render_template('log.html', lines=lines)

@app.route('/admin')
@login_required
def view_admin():
  return flask.render_template('admin.html')

@app.route('/reminders/new')
@login_required
def new_job():
  return flask.render_template('new_job.html', title=TITLE)

@app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

@app.route('/reminders/request/execute/<job_id>')
@login_required
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.execute_job.apply_async((job_id, ), queue=DB_NAME)

  return 'OK'
