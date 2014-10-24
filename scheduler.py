from datetime import datetime,timedelta
import time
import pymongo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import tasks

#-------------------------------------------------------------------
def fire_job(job_id):
    print "Scheduled: %s" % job_id
    tasks.validate_message(job_id)

#-------------------------------------------------------------------
if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.start()

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']

    print "Scheduler started"

    time.sleep(2)

    while True:
        cursor = db['call_jobs'].find({'status':True})
        for each in cursor:
            time_delta = each['fire_dtime'] - datetime.now()

            if  time_delta > timedelta(0,0,0,0,1,0,0):
                print "Adding %s to queue." % each['_id']
                
                scheduler.add_job(
                  func=fire_job, 
                  trigger=DateTrigger(run_date=each['fire_dtime']),
                  args=[each['_id']]
                )
                print scheduler.print_jobs()
            else:
                print "Rejecting %s from queue." % each['_id']
            
            # Change record status to inactive

            query = {'$set':{'status':False}}
            db['call_jobs'].update({'_id':each['_id']}, query)


        time.sleep(10)
