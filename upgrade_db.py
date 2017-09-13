"""
Step 1. Export Stats Gsheet data to JSON file
Step 2. Import JSON file to db: import_json_stats()
Step 3. Update route documents to new format: upgrade_routes()
Step 4. Add Stats data to the routes: add_stats()
"""

import json
from bson.json_util import dumps
from pprint import pprint
from dateutil.parser import parse
from datetime import timedelta, datetime, time, date
from mongo import create_client

#-------------------------------------------------------------------------------
def import_json_stats():

    with open('stats.json') as data_file:
        data = json.load(data_file)
        print 'file loaded. %s entries' % len(data)

        db_client = create_client()
        db = db_client['test']


        for i in range(len(data)):
            data[i]['date'] = parse(data[i]['date'])
            db['gsheets'].insert_one(data[i])

        print 'inserted all entries'

#-------------------------------------------------------------------------------
def upgrade_routes():
    # Copy documents in db['routes'] to db['new_routes'] collection and upgrade
    # to new format.

    client = create_client()
    db = client['bravo']
    routes = db['routes'].find({'group':'vec'}).sort('date',1)
    routes = list(routes)
    print '\nQueried %s routes to rebuild.' % len(routes)
    print 'Rebuilding...'
    n_inserts = 0

    for i in range(len(routes)):
        route = routes[i]

        try:
            res = db['new_routes'].insert_one({
                "date": route.get('date',None),
                "block": route.get('block',None),
                "group":'vec',
                "stats": {
                    "nBlockAccounts" :    route.get('block_size',None),
                    "nOrders" :           route.get('orders',None),
                    "nDropoffs" :         route.get('dropoffs',None),
                    "nSkips" :            route.get('no_pickups',None),
                    "nDonations" :        None,
                    "nZeros" :            None,
                    "receiptTotal" :      None,
                    "estimateAvg" :       None,
                    "estimateTotal" :     None,
                    "collectionRate" :    None,
                    "receiptAvg" :        None,
                    "estimateTrend" :     None,
                    "estimateMargin" :    None
                },
                "routific": {
                    "jobID" :          route.get('job_id',None),
                    "status" :         route.get('status',None),
                    "nOrders" :        route.get('orders',None),
                    "nUnserved" :      route.get('num_unserved',None),
                    "travelDuration" : route.get('total_travel_time',None),
                    "totalDuration" :  route.get('duration',None),
                    "startAddress" :   route.get('start_address',None),
                    "endAddress" :     route.get('end_address',None),
                    "driver" :         route.get('driver',None),
                    "depot" :          route.get('depot',None),
                    "postal" :         route.get('postal',None),
                    "warnings" :       route.get('warnngs',None),
                    "errors" :         route.get('errors',None),
                    "orders" :         None
                },
                "driverInput": {
                    "invoiceNumber":None,
                    "mileage" :     None,
                    "raName" :      None,
                    "driverName" :  None,
                    "vehicle" :     None,
                    "raHrs" :       None,
                    "driverHrs" :   None,
                    "vehicleInspection": None,
                    "notes" :       None,
                    "nCages" :      None
                }
            })
        except Exception as e:
            print 'i=%s, date=%s, block=%s, status=FAILED, error=%s' %(
                i, route['date'], route['block'], res.inserted_id, str(e))
        else:
            if res.inserted_id:
                n_inserts+=1
                print 'i=%s, date=%s, block=%s, status=SUCCESS, inserted_id=%s' %(
                    i,route['date'],route['block'],res.inserted_id)

    print 'Done.\nInserted %s out of %s documents.\n' %(n_inserts, len(routes))

#-------------------------------------------------------------------------------
def add_stats():
    # Add stat and driver input data to db['new_routes']
    # Data source test.db['gsheets'] (imported from Google Sheets JSON dump)

    db_client = create_client()
    db = db_client['test']
    stats = db['gsheets'].find({}).sort('date',1)
    print 'Queried %s db.gsheets documents' % stats.count()
    stats = list(stats)
    db = db_client['bravo']
    nUpdatedDocs = 0
    nUpdateErrors = 0
    nMissingKeys = 0
    nMatchFails = 0

    for i in range(len(stats)):
        doc = stats[i]

        if not doc.get('date') or not doc.get('block'):
            print 'Missing date/block. Skipping record'
            nMissingKeys+=1
            continue

        doc['date'] += timedelta(hours=8)

        route = db['new_routes'].find_one(
            {'group':'vec', 'date':doc['date'], 'block':doc['block']})

        if not route:
            nMatchFails+=1
            continue

        try:
            res = db['new_routes'].update_one(
                {'_id':route['_id']},
                {'$set': {
                    'stats.nDonations':             doc.get("donors",None),
                    'stats.nZeros':                 doc.get("zeros",None),
                    'stats.estimateTotal':          doc.get("estmt",None),
                    'stats.receiptTotal':           doc.get("receipt",None),
                    'stats.estimateAvg':            doc.get("donAvg",None),
                    'stats.collectionRate':         doc.get("collectRate",None),
                    'stats.estimateMargin':         doc.get("estmtMargin",None),
                    'stats.estimateTrend':          doc.get("estmtTrend",None),
                    'driverInput.invoiceNumber':    doc.get("invoice",None),
                    'driverInput.mileage':          doc.get('mileage',None),
                    'driverInput.raName':           doc.get('ra',None),
                    'driverInput.driverName':       doc.get('driver',None),
                    'driverInput.vehicle':          doc.get('vehicle',None),
                    'driverInput.raHrs':            doc.get('raHrs', None),
                    'driverInput.driverHrs':        doc.get('driverHrs',None),
                    'driverInput.vehicleInspection': doc.get('inspection',None),
                    'driverInput.notes':            doc.get('routeNotes', None),
                    'driverInput.nCages':           doc.get("cages",None),
                }}
            )
        except Exception as e:
            print 'i=%s, date=%s, block=%s, status=FAILED, error=%s'%(
                i, route['date'], route['block'], str(e))
            nUpdateFails+=1
        else:
            print 'i=%s, date=%s, block=%s, nModified=%s'%(
                i, route['date'], route['block'], res.modified_count)
            nUpdatedDocs += res.modified_count

    print 'Done. nUpdatedDocs=%s, nUpdateErrors=%s, nMatchFails=%s, nMissingKeys=%s' %(
        nUpdatedDocs, nUpdateErrors, nMatchFails, nMissingKeys)


#-------------------------------------------------------------------------------
if __name__ == "__main__":

    pass



#-------------------------------------------------------------------------------
"""MongoDB document formats

# test.db['gsheets'] documents:
{
    "_id" : ObjectId("59b36f2d4da93a22532cab95"),
    "date" : ISODate("2017-09-05T06:00:00.000Z"),
    "block" : "R8B"
    "skips" : 44,
    "drops" : 1,
    "orders" : 75,
    "donors" : 46,
    "zeros" : 25,
    "estmt" : 737.5,
    "receipt": 494,
    "donAvg": 44,
    "collectRate" : 0.647887323943662,
    "estmtMargin" : "-",
    "estmtTrend" : 8.1195652173913,
    "invoice" : 4083,
    "cages" : 8,
    "driver" : "James",
    "driverHrs" : 10.25,
    "ra" : "Derek",
    "raHrs" : 8.5,
    "vehicle" : "Ford",
    "mileage" : 47182,
    "inspection" : "ok",
    "routeNotes" : "unloadedFord first thing. fueled up.",
    "tripSched" : 5.6,
    "tripActual" : 7.25,
    "d" : 5,
    "m" : "Sep",
    "y" : 2017,
}

# db['routes'] documents:
{
    "_id" : ObjectId("59a952d84da93a07da35f930"),
    "date" : ISODate("2017-09-06T14:00:00.000Z"),
    "block" : "R8C",
    "group" : "vec",
    "dropoffs" : 0,
    "block_size" : 55,
    "no_pickups" : 11,
    "depot" : {},
    "driver" : {},
    "errors" : [],
    "postal" : ["T3H"],
    "warnings" : [],
    "start_address" : "3304 33 St NW, Calgary, AB",
    "end_address" : "3304 33 St NW, Calgary, AB",
    "job_id" : "j7905rnr121",
    "status" : "finished",
    "orders" : 44,
    "num_unserved" : 0,
    "total_travel_time" : 194,
    "duration" : 328,
    "routific" : {
        "input" : {},
        "solution" : {}
    },
    "ss" : {}
}

# db['new_routes'] documents:
{
    "_id" : "ObjectId(59b6c77e4da93a19652ee135)",
    "date" : {"$date":1505168551187},
    "block" : "R2F",
    "group" : "wsf",
    "stats" : {
        "nOrders" : 68,
        "receiptTotal" : null,
        "estimateAvg" : null,
        "estimateTotal" : null,
        "collectionRate" : null,
        "receiptAvg" : null,
        "nDropoffs" : 0,
        "nBlockAccounts" : 83,
        "estimateTrend" : null,
        "nZeros" : null,
        "nDonations" : null,
        "nSkips" : null,
        "estimateMargin" : null
    },
    "routific" : {
        "status" : "pending",
        "nUnserved" : null,
        "nOrders" : null,
        "warnings" : [],
        "driver" : {},
            "shift_start" : "08:00",
            "name" : "Default"
        },
        "startAddress" : null,
        "postal" : "",
        "orders" : [],
        "errors" : [],
        "endAddress" : null,
        "jobID" : null,
        "travelDuration" : null,
        "depot" : {},
        "totalDuration" : null
    },
    "driverInput" : {
        "invoiceNumber" : null,
        "mileage" : null,
        "raName" : null,
        "driverName" : null,
        "vehicle" : null,
        "raHrs" : null,
        "driverHrs" : null,
        "vehicleInspection" : null,
        "notes" : null,
        "nCages" : null
    }
}


"""
