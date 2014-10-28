import os
import logging

# TODO: Create a mongodb settings collection and webpage to manage these values

FROM_NUMBER= '+17804138846'
CALLER_ID= 'Winnifred Stewart Association'
BROKER_URI= 'amqp://'
URL= 'http://23.239.21.165:5000'
COUNTER_URL='http://23.239.21.165/call/1'
AUTH_ID= 'MAMGFLNDVJMWE0NWU2MW'
AUTH_TOKEN= 'ZGFjOTEyN2RjMjBlZjU0YzY1NDg2MTc2ZjkyMzA5'
CPS= 1
MAX_ATTEMPTS= 3
EMAIL_USER = 'winnstew'
EMAIL_PW = 'batman()'


def setLogger(logger, level, log_name):
    handler = logging.FileHandler(log_name)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
