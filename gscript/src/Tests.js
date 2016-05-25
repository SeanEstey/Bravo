//---------------------------------------------------------------------
function main() {
  //runModuleTests(GeoTests);
  //runModuleTests(ScheduleTests);
  //runModuleTests(SignupsTests);
  runModuleTests(RouteProcessorTests, false);
  //runModuleTests(RouteTests);
}

//---------------------------------------------------------------------
function runModuleTests(module, mute_log) {
  /* Runs all tests within module object, where a test is any function without
   * a leading underscore in its name.
   * @mute_log: optional bool argument to mute non-test logs, showing only
   * testing output. True by default.
   */
  
  if(mute_log == undefined)
    mute_log = true;
  
  var log_lines = [];
  
  log_lines.push("***** Running " + module['name'] + " Unit Tests *****");
  
  var n_fails = 0;
  var n_passes = 0;
  
  var old_log = Logger.getLog();
  
  for(var f in module) {    
    try {
      if(typeof(module[f]) != "function")
        continue;
      
      // Skip non-test functions like _init()
      if(f[0] == "_")
        continue;
      
      if(module[f]()) {
        n_passes++;
        log_lines.push(f + "...passed");
      }
      else {
        log_lines.push(f + "...FAILED");
        n_fails++;
      }
    }
    catch(e) {
      n_fails++;
      var e_msg = e.message+" file: " + e.fileName + ".gs, line: " + e.lineNumber;  
      log_lines.push(f + "...Exception! (" + e_msg + ")");
    }
  }
 
  
  if(mute_log) {
    Logger.clear();
    
    old_log = old_log.replace(/.{29}INFO\:/g, "???");
    old_log = old_log.split("???");
    
    for(var i=0; i < old_log.length; i++) {
      if(old_log[i] && old_log[i].length > 0)
        Logger.log(old_log[i].trim());
    }
  }
  
  for(var i=0; i<log_lines.length; i++) {
    Logger.log(log_lines[i]);  
  }
  
  Logger.log(
    "%s tests failed (%s ran)", 
    Number(n_fails).toString(),
    Number(n_passes+n_fails).toString());
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
var RouteTests = {
  "name": "Route",
  "orderToDict": function() {
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    return typeof(r.orderToDict(1)) == "object";
  },
  "orderToDict (invalid)": function() {
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    return r.orderToDict(100) == false;
  },
  "getInfo": function() {
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    return r.getInfo();
  },
  "getInventoryChanges": function() {
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    return r.getInventoryChanges();
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
  "getPickupDates": function() {
    var rp = RouteProcessorTests._init();
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    return rp.getPickupDates(r);
  },
  "getPickupDates (invalid)": function() {
    var rp = RouteProcessorTests._init();
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    r.orders[0][r.headers.indexOf('Block')] += ", B18F";
    return rp.getPickupDates(r) == false;
  },
  "getNextPickup": function() {
    var rp = RouteProcessorTests._init();
    var r = new Route("1Nk0BF84Wbu5oWJS4eix3CCh1bIJddPNgFmuWgmF8Txc");
    rp.getPickupDates(r);
    return rp.getNextPickup(r.orders[0][r.headers.indexOf('Block')]);
  },
  "importRoute": function() {
    return true;
  },
  "processRow": function() {
    return true;
  },
  "archive": function() {
    return true;
  },
  "uploadEntries": function() {
    return true;
  },
  "sendReceipts": function() {
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
  "assignNaturalBlock": function() {
    var s = SignupsTests._init();
    return s.assignNaturalBlock(0);
  },
  "assignBookingBlock": function() {
    var s = SignupsTests._init();
    s.signups_values[0][s.headers.indexOf('Natural Block')] = 'R3E';
    return s.assignBookingBlock(0);                              
  },
  "validateEmail (valid)": function() {
    var s = SignupsTests._init();
    return (s.validateEmail(0) == true);
  },
  "validateEmail (invalid)": function() {
    var s = SignupsTests._init();
    s.signups_values[0][s.headers.indexOf('Email')] = "foo@";
    return (s.validateEmail(0) == false);
  },
  "validatePhone (valid)": function() {
    var s = SignupsTests._init();
    s.signups_values[0][s.headers.indexOf('Primary Phone')] = "780-453-6707";
    return (s.validatePhone(0) == true);
  },
  "validatePhone (invalid)": function() {
    var s = SignupsTests._init();
    s.signups_values[0][s.headers.indexOf('Primary Phone')] = "555-555-5555";
    return (s.validatePhone(0) == false);
  },

  
  "_init": function() {
    return new Signups(
      TestData['map_data'], {
        'twilio_auth_key': JSON.parse(PropertiesService.getScriptProperties().getProperty("twilio_auth_key")), 
        'booking':TestConfig['booking'],
        'etapestry': JSON.parse(PropertiesService.getScriptProperties().getProperty("etapestry")),
        'cal_ids': TestConfig['cal_ids'], 
        'gdrive': TestConfig['gdrive']
      },
      TestData['res_cal_events']
    );
  }
};