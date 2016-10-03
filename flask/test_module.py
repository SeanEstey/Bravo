from bson.objectid import ObjectId
import pymongo
from dateutil.parser import parse
from datetime import datetime, date, time
import json

from app import app

agency = 'vec'


client = pymongo.MongoClient('localhost', 27017)
db = client['bravo']
agency_conf = db['agencies'].find_one({'name':agency})

import notific_events
import triggers
import notifications
import etap
import utils
import tasks
import pickup_service

#pickup_service.schedule_reminder_events()

event_id = ObjectId("57f2ae87fd9ab4312024a8c7")
email_trig_id = ObjectId("57f2ae87fd9ab4312024a8c8")
email_notify_id = ObjectId("57f2ae87fd9ab4312024a8cb")

phone_trig_id = ObjectId("57f2ae87fd9ab4312024a8c9")
phone_notify_id = ObjectId("57f2ae87fd9ab4312024a8ca")


#db['notifications'].update_one({'_id':email_notify_id},{'$set':{'status':'pending'}})
#db['triggers'].update_one({'_id':email_trig_id},{'$set':{'status':'pending'}})
#triggers.fire(event_id, email_trig_id)


db['notifications'].update_one({'_id':phone_notify_id},{'$set':{'status':'pending','attempts':0}})
db['triggers'].update_one({'_id':phone_trig_id},{'$set':{'status':'pending'}})

tasks.fire_trigger.apply_async(
    (str(event_id), str(phone_trig_id)),
    queue=app.config['DB'])



#triggers.fire(event_id, phone_trig_id)








