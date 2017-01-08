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
    'error': {
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
        }
    }
}
