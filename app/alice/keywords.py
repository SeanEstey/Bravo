'''app.alice.keywords'''

user = {
    'SCHEDULE': {
        'on_receive': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'reply_schedule'
            }
        }
    },
    'SUPPORT': {
        'on_receive': {
            'action': 'reply',
            'dialog': \
                "Tell me what you need help with and I'll forward your "\
                "request to the right person."
        },
        'on_complete': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'request_support'
            }
        }
    },
    'INSTRUCTIONS': {
         'on_receive': {
            'action': 'reply',
            'dialog': \
                "Tell me what you'd like instructions to pass along to our driver"
        },
        'on_complete': {
            'action':'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'add_instruction',
            }
        }
    },
    'SKIP': {
        'on_receive': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'skip_pickup'
            }
        }
    }
}

anon = {
    'UPDATE': {
        'on_receive': {
            'action': 'reply',
            'dialog': \
                "I can identify your acount for you, I just need you to tell "\
                "me your current address"
        },
        'on_complete': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'update_mobile'
            }
        }
    },
    'REGISTER': {
        'on_receive': {
            'action': 'reply',
            'dialog': \
                "I can schedule you for pickup. What's your full address?"
        },
        'on_complete': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'request_pickup'
            }
        }
    }
}
