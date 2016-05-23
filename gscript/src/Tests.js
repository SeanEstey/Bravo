//---------------------------------------------------------------------
function main() {
  runTests(GeoTests);
  runTests(ScheduleTests);
  runTests(SignupsTests);
  runTests(RouteProcessorTests);
}

//---------------------------------------------------------------------
function runTests(module) {
  /* Run through all functions in module object, execute these tests */
  
  var log_lines = [];
  
  log_lines.push("***** Running " + module['name'] + " Unit Tests *****");
  
  var n_fails = 0;
  var n_passes = 0;
  
  var old_log = Logger.getLog();
  
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
  
  // Clear the log so only unit testing messages are visible
  
  Logger.clear();
  
  old_log = old_log.replace(/.{29}INFO\:/g, "???");
  old_log = old_log.replace(/\n/g, '');
  old_log = old_log.split("???");
 
  for(var i=0; i < old_log.length; i++) {
    if(old_log[i] && old_log[i].length > 0)
      Logger.log(old_log[i].trim());
  }
  
  for(var i=0; i<log_lines.length; i++) {
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
    return (GeoTests._blocksWithin(51.035519, -114.120903, 10, 7)).length == 0;
  },
  "findMapTitle": function() {
    return Geo.findMapTitle(53.499753, -113.546706, TestData['map_data']);
  },
  
  "_blocksWithin": function(lat, lng, radius, days) {
    return Geo.findBlocksWithin(
      lat, 
      lng, 
      TestData['map_data'], 
      radius, 
      new Date(new Date().getTime() + (1000 * 3600 * 24 * days)), 
      TestConfig['cal_ids']['res'],
      TestData['res_cal_events']
    );
  },
};

//---------------------------------------------------------------------
var ScheduleTests = {
  "name": "Schedule",
  "getEventsBetween": function() {
    return Schedule.getEventsBetween(
      TestConfig['etw_res_cal_id'], 
      new Date(), 
      new Date((new Date()).getTime() + 1000*3600*24*7));
  }
};

//---------------------------------------------------------------------
var RouteProcessorTests = {
  "name": "RouteProcessor",
  "processRow": function() {
    var rp = RouteProcessorTests._init();
    rp.pickup_dates = TestData['pickup_dates'];
    rp.processRow(TestData['route_row'], 1, new Date(), "Kevin");
    return true;
  },
  
  "_init": function() {
    return new RouteProcessor(
      TestConfig['gdrive']['ss_ids'], 
      TestConfig['cal_ids'], 
      TestConfig['gdrive']['folder_ids'], 
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
    return new Signups(
      TestData['map_data'], {
        'twilio_auth_key':'ABC', 
        'booking':TestConfig['booking'],
        'etapestry': JSON.parse(PropertiesService.getScriptProperties().getProperty("etapestry")),
        'cal_ids': TestConfig['cal_ids'], 
        'gdrive': TestConfig['gdrive']
      },
      TestData['res_cal_events']
    );
  }
};