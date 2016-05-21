function test_geocode() {
  Logger.log(geocode('411 Heffernan Drive NW, Edmonton, AB'));
}

function test_headers() {
 var sheet = SpreadsheetApp.openById('1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c'); 
  var headers = sheet.getSheetByName('Route').getRange('1:1').getValues()[0];
  Logger.log(headers);

}

function test_inven_update() {  
  var inventory_ss = SpreadsheetApp.openById(Config['gdrive']['ss_ids']['inventory']);
  var routeProcessor = new RouteProcessor();
  
  var ids = [
    '1iVGKcqf7Knq8Rlaf9Ol2KbEByPF_n5uLNrYSHB55g4I',
    '1DEy3hsxiIUWgidk4pv-a6Re1YT1DRG5A80WVerJOM_s',
    '1Sg8bt3S6TY4ZwEoKG8gPARVDan2SxliagoFFe6_vQBE',
    '1J_642LnU6zar0OBKbgxsQjgBEAFYNnpyEdzQA8JvnzY'
    ];
  
  for(var i=0; i<ids.length; i++) {
    var route = new Route(ids[i]);
    route.getInventoryChanges();
    updateInventory(inventory_ss, route);
  }
 
}

function test_route_get_info() {
  var route = new Route('1uRvRNJxl_1oVeNJJg-INDt2cdZbnHcxeUu_0OKWRQ_4');
//  Logger.log(route.getInventoryChanges());
  //Logger.log(route.getInfo());
    var routeProcessor = new RouteProcessor();

    
    routeProcessor.import(route);
  
  
}

function test_login_script() {
  var res = bravoPOST(BRAVO_PHP_URL, 'get_num_active_processes', {'ok':'ok'});
  Logger.log(res.getContentText() + ', code: ' + res.getResponseCode());
}

function test_gift_entries_constructor() {
  var entries = new RunProcessor();
  Logger.log(entries.headers);
}

function test_gift_entries_import_run() {
  var run = new Run('1RWINK1VyN_KQEY5ujMgFdaCmaMghtvUmF472GysQeb0');
  var entries = new RunProcessor();
  entries.import(run);
}

function test_gift_entries_getPickupDates() {
  var run = new Run('1RWINK1VyN_KQEY5ujMgFdaCmaMghtvUmF472GysQeb0');
  var entries = new RunProcessor();
  entries.getPickupDates(run);
}

function test_gift_entries_getNextPickup() {
  var run = new Run('1RWINK1VyN_KQEY5ujMgFdaCmaMghtvUmF472GysQeb0');
  var entries = new RunProcessor();
  var pickup_dates = entries.getPickupDates(run);
  
  Logger.log(entries.getNextPickup("R4P, B4A, R2A, B5A", pickup_dates));
  Logger.log(entries.getNextPickup("R4P", pickup_dates));
}

function test_gift_entries_process_run_row() {
  var row = {
    'account_num': 12345, 
    'name_or_address': '1234 5 st', 
    'driver_input': 'nh', 
    'gift': '$5', 
    'driver_notes': 'dropoff today', 
    'blocks': 'B4A, R5G, R7B',
    'neighborhood': 'Oliver', 
    'status': 'Dropoff', 
    'office_notes': '***RMV R5G*** no tax receipt'
  };
  var date = new Date();
  var entries = new RunProcessor();
  entries.process(row, 5, date, 'Ryan');
}

function test_update_stats() {
  var stats_archive_ss = SpreadsheetApp.openById(Config['gdrive']['ss_ids']['stats_archive']);
  var route = new Route('1e96IuRL0SrfDoccpDSB0F8MrbyrK3uANuz-e7PIXNho');
  var stats_ss = SpreadsheetApp.openById(Config['gdrive']['ss_ids']['stats']);
  updateStats(stats_ss, stats_archive_ss, route);
  
}
