'''app.notify.endpoints'''
import logging
from flask import g, jsonify, Response
from app.notify import pickups, recording, sms, voice
from . import notify
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/no_pickup', methods=['GET'])
def no_pickup(evnt_id, acct_id):
    if not pickups.is_valid(evnt_id, acct_id):
        log.error('event/acct not found (evnt_id=%s, acct_id=%s)', evnt_id, acct_id)
        return 'Sorry there was an error fulfilling your request'
    from app.notify.tasks import skip_pickup
    skip_pickup.delay(evnt_id, acct_id)
    return 'Thank You'

@notify.route('/record/answer.xml',methods=['POST'])
def record_xml():
    return Response(response=str(recording.on_answer()), mimetype='text/xml')

@notify.route('/record/interact.xml', methods=['POST'])
def record_interact_xml():
    return Response(response=str(recording.on_interact()), mimetype='text/xml')

@notify.route('/record/complete',methods=['POST'])
def record_complete():
    return jsonify(recording.on_complete())

@notify.route('/voice/play/answer.xml',methods=['POST'])
def get_call_answer_xml():
    return Response(str(voice.on_answer()), mimetype='text/xml')

@notify.route('/voice/play/interact.xml', methods=['POST'])
def get_call_interact_xml():
    return Response(str(voice.on_interact()), mimetype='text/xml')

@notify.route('/voice/complete', methods=['POST'])
def call_complete():
    return voice.on_complete()

@notify.route('/voice/fallback', methods=['POST'])
def call_fallback():
    return voice.on_error()

@notify.route('/sms/status', methods=['POST'])
def sms_status():
    return sms.on_status()

@notify.route('/call/nis', methods=['POST'])
def nis():
    from app.main.tasks import create_rfu
    record = request.get_json()
    create_rfu.delay(g.user.agency, '%s not in service' % record['custom']['to'],
        options={
            'Account Number': record['account_id'],
            'Block': record['custom']['block']})
