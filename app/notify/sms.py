'''notify.sms'''

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
        "sid": "49959jfd93jd"
    },
    "to" : "(403) 874-9467",
    "type" : "sms"
}'''


#-------------------------------------------------------------------------------
def send(notification, twilio_conf):
    '''Private method called by send()
    '''
    return True
