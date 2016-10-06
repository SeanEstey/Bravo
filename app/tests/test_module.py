from bson.objectid import ObjectId
import pymongo
from dateutil.parser import parse
from datetime import datetime, date, time
import json

#from app import app

agency = 'vec'


client = pymongo.MongoClient('localhost', 27017)
db = client['bravo']
agency_conf = db['agencies'].find_one({'name':agency})

from app.notify import notific_events

event_id = ObjectId("57f64ad7fd9ab44c64784ef3")
notific_events.get_grouped_notifications(event_id)

