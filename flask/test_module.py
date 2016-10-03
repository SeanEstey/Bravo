
import pymongo

client = pymongo.MongoClient('localhost', 27017)
db = client['bravo']

import notific_events
from datetime import date

notific_events.add('vec', 'R4A', date.today())

# Add imports for modules here to test for syntax error
# without having to run from flask

# import routing
