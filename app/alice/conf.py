'''app.alice.conf'''

actions = {
    'schedule': {
        'on_keyword': {
            'handler': {
                'module': 'app.main.alice',
                'func': 'reply_schedule'
            }
        },
        'on_reply': {}
    },
    'support': {
        'on_keyword': {
            'dialog': \
                "Tell me what you need help with and I'll forward your "\
                "request to the right person."
        },
        'on_reply': {
            'handler': {
                'module': 'app.main.alice',
                'func': 'do_support'
            }
        }
    },
    'instructions': {
        'on_keyword': {
            'dialog': \
                "Tell me what you'd like instructions to pass along to our driver"
        },
        'on_reply': {
            'handler': {
                'module': 'alice',
                'func': 'add_driver_note',
            }
        }
    },
    'skip': {
        'on_keyword': {
            'handler': {
                'module': 'alice',
                'func': 'skip_pickup'
            }
        },
        'on_reply': {}
    },
    'update': {
        'on_keyword': {
            'dialog': \
                "I can identify your acount for you, I just need you to tell "\
                "me your current address"
        },
        'on_reply': {
            'handler': {
                'module': 'alice',
                'func': 'update_mobile'
            }
        }
    },
    'register': {
        'on_keyword': {
            'dialog': \
                "I can schedule you for pickup. What's your full address?"
        },
        'on_reply': {
            'handler': {
                'module': 'alice',
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
    "general": {
        "intro": \
            "How can I help you?",
        "thanks_reply": \
            "You're welcome!"
    },
    "user": {
        "options": \
            "You can guide me with keywords. "\
            "Ask me about your pickup SCHEDULE, or request live SUPPORT.",
    },
    "unregistered": {
        "options": \
            "I don't recognize this number. "\
            "Do you have an account? I can UPDATE it for you. "\
            "If you're new, you can REGISTER for a pickup. "
    },
    "error": {
        "parse_question": \
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

