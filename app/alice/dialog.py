'''app.alice.dialog'''

dialog = {
    'user': {
        'options': \
            "You can guide me with keywords. "\
            "Ask me about your pickup SCHEDULE, or request live SUPPORT.",
        'welcome':\
            "I'll be your digital assistant for the pickup service. Text me "\
            "anytime if you need your schedule. Save me to your contact list "\
            "if you'd like. ",
        'joke_welcome':\
            "You're looking especially sexy today. You make my circuits "\
            "overheat..."
    },
    'anon': {
        'options': \
            "I don't recognize this number. "\
            "Do you have an account? I can UPDATE it for you. "#\
            #"If you're new, you can REGISTER for a pickup. "
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
        'prompt': \
            "Tell me what you'd like instructions to pass along to our driver",
        'thanks':\
            "Thank you. I'll pass along the note to our driver.",
        'no_evnt':\
            "I can't find an upcoming event to add your note onto. "
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
        'etap': {
            'lookup': \
                "I'm sorry, there seems to be a problem looking up "\
                "your account. We'll look into the matter for you.",
            'inactive':\
                "I'm sorry, your account seems to be inactive."
        }
    }
}
