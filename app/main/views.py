'''app.main.views'''
import logging
from flask import g, request, render_template, redirect, url_for, jsonify, Response
from flask_login import login_required
from .. import get_logger, get_keys
from app.lib import html
from . import main
log = get_logger('main.views')

#-------------------------------------------------------------------------------
@main.route('/')
def landing_page():
    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    if g.user.admin == True:
        settings = get_keys()
        settings.pop('_id')
        settings['google'].pop('oauth')
        settings_html = html.to_div('', settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)

#-------------------------------------------------------------------------------
@main.route('/preview', methods=['GET', 'POST'])
def view_client():
    log.debug('request.method=%s', request.method)

    if request.method == 'GET':
        from twilio.util import TwilioCapability

        keys = get_keys('twilio',agcy='vec')
        capability = TwilioCapability(keys['api']['sid'], keys['api']['auth_id'])
        app_sid = "AP30ab394c8e7460fac579d5559a8d4cb7"
        capability.allow_client_outgoing(app_sid)
        capability.allow_client_incoming("jenny")
        token = capability.generate()
        log.debug('generated token, sending to client...')

        return render_template('/views/preview.html', token=token)
    elif request.method == 'POST':
        log.debug(request.form.to_dict())
        from app.notify.voice import get_speak
        from twilio import twiml

        notific = g.db.notifics.find_one({'type':'voice'})
        notific['tracking']['answered_by'] = 'human'
        notific['tracking']['digit'] = "1"
        acct = g.db.accounts.find_one({'_id':notific['acct_id']})
        speak = get_speak(notific, notific['on_answer']['template'], timeout=False)
        response = twiml.Response()
        response.say(speak, voice='alice')
        return Response(str(response), mimetype='text/xml')
