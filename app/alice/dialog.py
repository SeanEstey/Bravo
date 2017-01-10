'''app.alice.dialog'''

dialog = {
    'user': {
        'options': \
            "You can guide me with keywords. "\
            "Ask me about your pickup SCHEDULE, or request live SUPPORT.",
    },
    'anon': {
        'options': \
            "I don't recognize this number. "\
            "Do you have an account? I can UPDATE it for you. "\
            "If you're new, you can REGISTER for a pickup. "
    },
    'general': {
        'intro': \
            "How can I help you?",
        'welcome_reply': \
            "You're welcome!"
    },
    'schedule': {
        'next': \
            "Your next scheduled pickup is on %s."
    },
    'support': {
        'thanks':\
            "Thank you. I'll have someone contact you soon."
    },
    'instruct': {
        'thanks':\
            "Thank you. I'll pass along the note to our driver."
    },
    'skip': {
        'success': \
            "Thank you. You have been removed from the route. ",
        'too_late': \
            "I'm sorry, I can't remove you from this route "\
            "as it has already been dispatched to our driver.",
        'no_evnt': \
            "I can't find an upcoming event to remove you from. "
    },
    'error': {
        'unknown':\
            "There a problem handling your request.",
        'parse': {
            'question': \
                "I don't quite understand your question.",
            'comprehend': \
                "Sorry, I don't understand. You can help guide me "\
                "with keywords."
        },
        'internal': {
            'default':\
                "There a problem handling your request.",
            'lookup':\
                "I'm sorry, there seems to be a problem looking up "\
                "your account. We'll look into the matter for you."
        },
        'etap': {
            'lookup': \
                "I'm sorry, there seems to be a problem looking up "\
                "your account. We'll look into the matter for you.",
            'inactive':\
                "I'm sorry, your account seems to be inactive."
        }
    }
}
