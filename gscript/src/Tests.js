//---------------------------------------------------------------------
function main() {
 runTests(GeoTests);
 runTests(ScheduleTests);
 runTests(RouteProcessorTests);
 runTests(SignupsTests);
}

//---------------------------------------------------------------------
function runTests(module) {
  /* Run through all functions in module object, execute these tests */
  
  Logger.log("*** Running %s Unit Tests ***", module['name']);
  
  var n_fails = 0;
  var n_passes = 0;
  
  var old_log = Logger.getLog();
  var log_lines = [];

  for(var f in module) {    
    if(typeof(module[f]) != "function")
       continue;
    
    // Skip non-test functions like _init()
    if(f[0] == "_")
      continue;
       
    if(module[f]()) {
      n_passes++;
      log_lines.push(f + "...SUCCESS");
    }
    else {
      log_lines.push(f + "...FAILED");
      n_fails++;
    }
  }
  
  // Clear any output so we can view only unit test log info
  Logger.clear();
  
  Logger.log(old_log);
  
  for(var i in log_lines) {
    Logger.log(log_lines[i]);
  }
  
  Logger.log("%s tests passed, %s tests failed", 
             Number(n_passes).toString(), 
             Number(n_fails).toString());
}


/******************************* TESTS *****************************/


//---------------------------------------------------------------------
var GeoTests = {
  "name": "Geo",
  "geocode": function() {
    return Geo.geocode('411 Heffernan Drive NW, Edmonton, AB') ||
           Geo.geocode('8 Garden Crescent, St Albert, AB') ||
           Geo.geocode('979 Fir Street, Sherwood Park, AB'); 
  },
  "findBlocksWithin": function() {
    return (GeoTests._blocksWithin(53.499753, -113.546706, 10, 90)).length > 0;
  },
  "findBlocksWithin_invalid": function() {
    return (GeoTests._blocksWithin(51.035519, -114.120903, 10, 7)).length > 0;
  },
  
  "_blocksWithin": function(lat, lng, radius, days) {
    return Geo.findBlocksWithin(
      lat, lng, 
      TestVars['map_data'], 
      radius, 
      new Date(new Date().getTime() + (1000 * 3600 * 24 * days)), 
      TestVars['cal_ids']['res']);
  },
};

//---------------------------------------------------------------------
var ScheduleTests = {
  "name": "Schedule",
  "getCalEventsBetween": function() {
    return Schedule.getCalEventsBetween(
      TestVars['etw_res_cal_id'], 
      new Date(), 
      new Date((new Date()).getTime() + 1000*3600*24*7));
  }
};

//---------------------------------------------------------------------
var RouteProcessorTests = {
  "name": "RouteProcessor",
  "processRow": function() {
    var rp = RouteProcessorTests._init();
    rp.pickup_dates = TestVars['pickup_dates'];
    rp.processRow(TestVars['route_row'], 1, new Date(), "Kevin");
    return true;
  },
  
  "_init": function() {
    return new RouteProcessor(
      TestVars['gdrive']['ss_ids'], 
      TestVars['cal_ids'], 
      TestVars['gdrive']['folder_ids'], 
      JSON.parse(PropertiesService.getScriptProperties().getProperty("etapestry")));  
  }
};

//---------------------------------------------------------------------
var SignupsTests = {
  "name": "Signups",
  "assignBookingBlock": function() {
    var s = SignupsTests._init();
    return s.assignBookingBlock(1);                              
  },
  
  "_init": function() {
    return new Signups({
      'twilio_auth_key':'ABC', 
      'booking':TestVars['booking'],
      'etapestry': JSON.parse(PropertiesService.getScriptProperties().getProperty("etapestry")),
      'cal_ids': TestVars['cal_ids'], 
      'gdrive': TestVars['gdrive']}, 
      TestVars['map_data']);
  }
};


/***************************** TEST DATA *****************************/


//---------------------------------------------------------------------
var TestVars = {
  "route_id": "1nLxNgkkCtXftPzASc09RRO29bJGqU2PI3UGcnrsz0LY", // May 18: B6C (Rod) 
  "edmonton_address": "411 Heffernan Drive NW, Edmonton, AB",
  "etw_res_cal_id": "7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com",
  "testGeocode": function() {
  },
  "gdrive": {
    "ss_ids": {
      'bravo': '1JjibGqBivKpQt4HSW0RFfuTPYAI9LxJu-QOd6dWySDE',   // DEV_SS
      'stats': '1iBRJOkSH2LEJID0FEGcE3MHOoC5OKQsz0aH4AAPpTR4',
      'stats_archive': '1BTS-r3PZS3QVR4j5rfsm6Z4kBXoGQY8ur60uH-DKF3o',
      'inventory': '1Mb6qOvYVUF9mxyn3rRSoOik427VOrltGAy7LSIR9mnU',
      'route_template': '1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c'
    },
    'folder_ids': {
      'routed': '0BxWL2eIF0hwCRnV6YmtRLVBDc0E',
      'entered': '0BxWL2eIF0hwCOTNSSy1HcWRKUFk'
    },
  },
  "cal_ids": {
    'res': '7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com',
    'bus': 'bsmoacn3nsn8lio6vk892tioes@group.calendar.google.com'
  },
  "pickup_dates": {
    "B4A": new Date("Oct 24, 2015"),
    "R5G": new Date("Dec 24, 2015"),
    "R7B": new Date("Sep 24, 2015")
  },
  "route_row": {
    'name_or_address': '1234 5 st',
    'gift': '5',
    'driver_input': 'nh', 
    'order_info': '_placeholder_',
    'account_num': 12345, 
    'driver_notes': 'dropoff today', 
    'blocks': 'B4A, R5G, R7B',
    'neighborhood': 'Oliver', 
    'status': 'Dropoff', 
    'office_notes': '***RMV R5G*** no tax receipt'
  },
  'booking': {
    'max_block_radius': 10,
    'max_schedule_days_wait': 14,
    'search_weeks': 16,
    'size': {
      'res': {
        'medium': 60,
        'large': 75,
        'max': 90,
      },
      'bus': {
        'medium': 20,
        'large': 23,
        'max': 25
      }
    }
  },
  "map_data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Polygon",
          "coordinates": [
            [
              [
                -113.5555673,
                53.502387,
                0
              ],
              [
                -113.5570264,
                53.501365899999996,
                0
              ],
              [
                -113.5565114,
                53.49748580000001,
                0
              ],
              [
                -113.5411048,
                53.4975113,
                0
              ],
              [
                -113.5411477,
                53.5044034,
                0
              ],
              [
                -113.5438943,
                53.5047097,
                0
              ],
              [
                -113.5461259,
                53.50302510000001,
                0
              ],
              [
                -113.5555673,
                53.502387,
                0
              ]
            ]
          ]
        },
        "properties": {
          "name": "R3E [Grandview Heights]",
          "description": "gx_image_links: ",
          "gx_image_links": ""
        }
      }
    ]
  }
};