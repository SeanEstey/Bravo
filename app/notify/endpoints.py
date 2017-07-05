'''app.notify.endpoints'''
from flask import g, jsonify, Response
from app.notify import pickups, recording, sms, voice
from . import notify
from logging import getLogger
log = getLogger(__name__)

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

@notify.route('/voice/preview', methods=['POST'])
def call_preview():
    return Response(str(voice.preview()), mimetype='text/xml')

@notify.route('/sms/status', methods=['POST'])
def sms_status():
    return sms.on_status()

@notify.route('/call/nis', methods=['POST'])
def nis():
    from app.main.tasks import create_rfu
    record = request.get_json()
    create_rfu.delay(
        g.group,
        '%s not in service' % record['custom']['to'],
        options={
            'ID': record['account_id'],
            'Block': record['custom']['block']})
