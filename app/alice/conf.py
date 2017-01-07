'''app.alice.conf'''

# For identified users
user_keywords = {
    'schedule': {
        'on_receive': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'reply_schedule'
            }
        }
    },
    'support': {
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
                'func': 'do_support'
            }
        }
    },
    'instructions': {
         'on_receive': {
            'action': 'reply',
            'dialog': \
                "Tell me what you'd like instructions to pass along to our driver"
        },
        'on_complete': {
            'action':'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'add_driver_note',
            }
        }
    },
    'skip': {
        'on_receive': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'skip_pickup'
            }
        }
    }
}

# For unidentified users
anon_keywords = {
    'update': {
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
    'register': {
        'on_receive': {
            'action': 'reply',
            'dialog': \
                "I can schedule you for pickup. What's your full address?"
        },
        'on_complete': {
            'action': 'event',
            'handler': {
                'module': 'app.alice.events',
                'func': 'pickup_request'
            }
        }
    }
}

conversation_endings = [
    'THANKS',
    'THANK YOU',
    'THX',
    'SOUNDS GOOD',
    'OK'
]

dialog = {
    "user": {
        "options": \
            "You can guide me with keywords. "\
            "Ask me about your pickup SCHEDULE, or request live SUPPORT.",
    },
    "anon": {
        "options": \
            "I don't recognize this number. "\
            "Do you have an account? I can UPDATE it for you. "\
            "If you're new, you can REGISTER for a pickup. "
    },
    "general": {
        "intro": \
            "How can I help you?",
        "thanks_reply": \
            "You're welcome!"
    },
    "error": {
        "parse": \
            "I don't quite understand your question. ",
        "acct_lookup": \
            "I'm sorry, there seems to be a problem looking up "\
            "your account. We'll look into the matter for you.",
        "comprehension": \
            "Sorry, I don't understand your request. You'll have to guide "\
            "our conversation using keywords.",
        "unknown": \
            "There a problem handling your request."
    }
}

