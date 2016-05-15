//---------------------------------------------------------------------
// Take a list of spreadsheet_id's, import the routes, update stats and inventory,
// archive into 'Entered' folder.
function processRouteList(file_id_list) {
  var app = UiApp.getActiveApplication();
  var stats_ss = SpreadsheetApp.openById(Config['stats_ss_id']);
  var stats_archive_ss = SpreadsheetApp.openById(Config['stats_archive_ss_id']);
  var inventory_ss = SpreadsheetApp.openById(Config['inventory_ss_id']);
  app.close();
  var routeProcessor = new RouteProcessor();
  
  for(var i=0; i<file_id_list.length; i++) {
    var ss_id = file_id_list[i];
    
    var route = new Route(ss_id);
    
    routeProcessor.import(route);
    
    updateStats(stats_ss, stats_archive_ss, route);
    
    updateInventory(inventory_ss, route);
    
    routeProcessor.archive(route.id);
  }
}


//---------------------------------------------------------------------
function Route(id) {
  this.id = id;
  this.ss = SpreadsheetApp.openById(id);
  this.sheet = this.ss.getSheets()[0];
  
  var num_orders = this.sheet.getRange("E1:E")
    .getValues().filter(String).length - 1;
  
  // Chop off header row and Depot row (last)
  this.orders = this.sheet.getDataRange().getValues().slice(1, num_orders+1);
  
  // Route title format: "Dec 27: R4E (Ryan)"
  this.title = this.ss.getName();
  this.title_block = Parser.getBlockFromTitle(this.title);
     
  var date_str = this.title.substring(0, this.title.indexOf(":"));
  var full_date_str = date_str + ", " + (new Date()).getFullYear();
  this.date = new Date(full_date_str);
  this.driver = this.title.substring(
    this.title.indexOf("(")+1, 
    this.title.indexOf(")")
  );
   
  Logger.log('New Route block: ' + this.title_block);
    
  this.months = [
    "Jan", 
    "Feb", 
    "Mar", 
    "Apr", 
    "May", 
    "Jun", 
    "Jul", 
    "Aug", 
    "Sep", 
    "Oct", 
    "Nov", 
    "Dec"
  ];
}

//---------------------------------------------------------------------
/* Gather Stats and Inven fields from bottom section of Route, build dictionary: 
{
  "inventory": {
    "Bag Buddies In": 3,
    "Bag Buddies Out": 0,
    ...
  },
  "stats": {
    "Mileage": 55150,
    "Depot": "Strathcona",
    ...
  }
}
*/
Route.prototype.getInfo = function() {  
  var a = this.sheet.getRange(
    this.orders.length+3,
    1,
    this.sheet.getMaxRows()-this.orders.length+1,
    1).getValues();

  // Make into 1D array of field names: ["Total", "Participants", ...]
  a = a.join('//').split('//');
 
  var start = a.indexOf('***Route Info***') + 1;
  a.splice(0, start);
  
  // Now left with Stats and Inventory field names
  
  stats_fields = a.splice(0, a.indexOf('***Inventory***'));
  
  var stats = {};
  
  var b = this.sheet.getRange(
    this.orders.length+3,
    2,
    this.sheet.getMaxRows()-this.orders.length+1,
    1).getValues();
  
  b.splice(0, start);
  
  for(var i=0; i<stats_fields.length; i++) {
    var key = stats_fields[i]; 
    stats[key] = b[i][0];
  }
  
  return stats;
}

//---------------------------------------------------------------------
Route.prototype.getInventoryChanges = function() {
  var a = this.sheet.getRange(1,1,this.sheet.getMaxRows(),1).getValues();
  var b = this.sheet.getRange(1,2,this.sheet.getMaxRows(),1).getValues();
  
  a = a.join('//').split('//');
  b = b.join('//').split('//');
  
 var inven_idx = a.indexOf('***Inventory***');
  
  a = a.slice(inven_idx + 1, a.length);
  b = b.slice(inven_idx + 1, b.length);

  /* TODO: Loop through spliced array, make dictionary of all fields and values without referencing them by name below */
  
  return {
    'Bag Buddies In': b[a.indexOf('Bag Buddies In')],
    'Bag Buddies Out': b[a.indexOf('Bag Buddies Out')],
    'Green Bags': b[a.indexOf('Green Bags')],
    'Green Logo Bags': b[a.indexOf('Green Logo Bags')],
    'White Bags': b[a.indexOf('White Bags')],
    'Green Bins In': b[a.indexOf('Green Bins In')],
    'Green Bins Out': b[a.indexOf('Green Bins Out')],
    'Blue Bins In': b[a.indexOf('Blue Bins In')],
    'Blue Bins Out': b[a.indexOf('Blue Bins Out')],
    'Bottle Bins In': b[a.indexOf('Bottle Bins In')],
    'Bottle Bins Out': b[a.indexOf('Bottle Bins Out')]
  };
}

//---------------------------------------------------------------------
function RouteProcessor() {
  this.ss = SpreadsheetApp.getActiveSpreadsheet();
  this.sheets = {
    'Routes': this.ss.getSheetByName('Routes'),
    'RFU': this.ss.getSheetByName('RFU'),
    'MPU': this.ss.getSheetByName('MPU'), 
  };
  this.headers = this.sheets['Routes'].getRange(1,1,1,this.sheets['Routes'].getMaxColumns()).getValues()[0];
  
  var today = new Date();
  var tomorrow = new Date(Date.now() + (1000 * 3600 * 24));
  var one_month = new Date(Date.now() + (1000 * 3600 * 24 * 7 * 4));
  var six_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 6));
  var sixteen_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 16));
  
  var res_events = Schedule.getCalEventsBetween(Config['res_calendar_id'], one_month, sixteen_weeks);
  var bus_events = Schedule.getCalEventsBetween(Config['bus_calendar_id'], tomorrow, six_weeks);
  this.calendar_events = res_events.concat(bus_events);
  
  this.calendar_events.sort(function(a, b) {
    return parseDate(a.start.date).getTime() - parseDate(b.start.date).getTime();
  });
  
  this.gifts = [];
  this.rfus = [];
  this.mpus = [];
  this.errors = [];
  this.pickup_dates = [];
}

//---------------------------------------------------------------------
// Updates all the stops then writes them to appropriate GiftEntry sheets
RouteProcessor.prototype.import = function(route) {
  this.gifts = [];
  this.rfus = [];
  this.mpus = [];
  this.errors = [];
  
  this.getPickupDates(route);
  
  // Process all Gifts, MPU's, No Pickups, etc
  
  for(var i=0; i<route.orders.length; i++) {
    try {  
      var order_info = route.orders[i][Config['route_format']['Order Info']['column']-1];
      var act_name_regex = /Name\:\s(([a-zA-Z]*?\s)*){1,5}/g;
      var account_name = '';
      
      // Parse Account Name from "Order Info" string
      if(act_name_regex.test(order_info))
         account_name = order_info.match(act_name_regex)[0] + '\n';    
      
      var row = {
        'account_num': route.orders[i][Config['route_format']['Account Number']['column']-1],
        'name_or_address': account_name + route.orders[i][Config['route_format']['Address']['column']-1],
        'gift': route.orders[i][Config['route_format']['Gift Estimate']['column']-1],
        'driver_input': route.orders[i][Config['route_format']['Driver Input']['column']-1],
        'driver_notes': route.orders[i][Config['route_format']['Driver Notes']['column']-1],
        'blocks': route.orders[i][Config['route_format']['Block']['column']-1],
        'neighborhood': route.orders[i][Config['route_format']['Neighborhood']['column']-1],
        'status': route.orders[i][Config['route_format']['Status']['column']-1],
        'office_notes': route.orders[i][Config['route_format']['Office Notes']['column']-1]
      };
      
      if(row['neighborhood'])
        row['neighborhood'] = row['neighborhood'].replace(/, /g, ',');
      
      if(row['blocks'])
        row['blocks'] = row['blocks'].replace(/, /g, ',');
      
      var res = this.process(row, i+1, route.date, route.driver);
      
      if(res)
        this.errors.push(res);
    }
    catch(e) {
      var msg = 
        route.title_block + ' import failed. \\n' +
        'Row ' + (i+1) + ': [' + route.rows[i].toString() + ']\\n' +
        'Msg: ' + e.message + '\\n' +
        'File: ' + e.fileName + '\\n' + 
        'Line: ' + e.lineNumber;    
      log(msg, true);
      Browser.msgBox(msg, Browser.Buttons.OK);
    }
  }
  
  appendRowsToSheet(this.sheets['Routes'], this.gifts, 1);
  appendRowsToSheet(this.sheets['RFU'], this.rfus, 1);
  appendRowsToSheet(this.sheets['MPU'], this.mpus, 1);
  
  // Print Import Summary
  
  var summary_msg = 
    route.title + ' import complete.\\n' +
    'Gifts: ' + String(this.gifts.length) + '\\n' +
    'RFUs: ' + String(this.rfus.length) + '\\n' +
    'MPUs: ' + String(this.mpus.length) + '\\n';       
      
  if(this.errors.length > 0)
    summary_msg += '\\nErrors: ' + this.errors
 
  Browser.msgBox(summary_msg, Browser.Buttons.OK);
  
  summary_msg = summary_msg.replace(/\\n/g, '  ');
  Logger.log('summary_msg: ' + summary_msg);
  log(summary_msg, true);
}

//---------------------------------------------------------------------
// Build a dictionary of all blocks referenced in the route with their next schedule date
// e.g. {'R3C': 'September 9, 2015', 'B4A': 'Dec 20, 2016'}
RouteProcessor.prototype.getPickupDates = function(route) {
  this.pickup_dates = {};
    
  for(var i=0; i<route.orders.length; i++) {
    var row = route.orders[i];
    var blocks = row[Config['route_format']['Block']['column']-1];
    blocks = blocks.split(', ');
    
    for(var j=0; j<blocks.length; j++) {
      if(!this.pickup_dates.hasOwnProperty(blocks[j]))
        this.pickup_dates[blocks[j]] = Schedule.getNextBlock(this.calendar_events, blocks[j]).date;
    }
  }
    
  Logger.log('pickup_dates: ' + JSON.stringify(this.pickup_dates));
}

//---------------------------------------------------------------------
// Find the soonest pickup from list of blocks
// blocks: string of comma separated blocks
// pickup_dates: json object of block: date matches
RouteProcessor.prototype.getNextPickup = function(blocks) {
  if(!blocks)
    return '';
  
  var dates = [];
  blocks = blocks.split(',');
  
  for(var i=0; i<blocks.length; i++) {
    if(this.pickup_dates.hasOwnProperty(blocks[i]))
      dates.push(this.pickup_dates[blocks[i]]);
  }
  
  if(dates.length == 0) {
    log('Error in RouteProcessor.getNextPickup: no date found.', true);
    return '';
  }
    
  // Sort chronologically.
  dates.sort(function(a, b) {
    return a.getTime() - b.getTime();
  });
  
  // Return earliest date
  return dates[0];
}

//---------------------------------------------------------------------
/* Process a line entry from a route */
RouteProcessor.prototype.process = function(row, row_num, date, driver, pickup_dates) { 
  
  /*** Test for invalid data ***/
  
  var errors = '';
  
  if(!isNumber(row['account_num']))
    errors += 'Stop #' + String(row_num) + ': Invalid Account #';
  
  if(!row['blocks'] || !Parser.isBlockList(row['blocks']))
    errors += 'Stop #' + String(row_num) + ': Missing or invalid Blocks';
  
  if(!row['status'])
    errors += 'Stop #' + String(row_num) + ': Missing Status';
  
  // Remove unecessary newlines or spaces
  row['driver_notes'] = String(row['driver_notes']).trim();
  row['office_notes'] = String(row['office_notes']).trim();
  row['driver_input'] = String(row['driver_input']).trim();
  
  /*** Now process ***/
  
  // Remove any necessary blocks from note with format: "***RMV R2P***"
  var matches = String(row['office_notes']).match(/\*{3}RMV\s(B|R)\d{1,2}[a-zA-Z]{1}\*{3}(\n|\r)?/g);
  
  if(matches) {
    for(var i=0; i<matches.length; i++) {
      var rmv_note = matches[i];
      var rmv_block = rmv_note.match(/(B|R)\d{1,2}[a-zA-Z]/g)[0];
      var block_list = row['blocks'].split(',');
      
      for(var j=0; j<block_list.length; j++) {
        if(block_list[j] == rmv_block)
          block_list.splice(j, 1);
      }
      row['blocks'] = block_list.join(',');
      row['office_notes'] = row['office_notes'].replace(rmv_note, '');
      Logger.log('replaced office notes: ['+row['office_notes']+']');
    }
  }
  
  // Clear any temporary Driver Notes surrounded by a set of '***' characters
  var temp_driver_notes = "";
  var matches = row['driver_notes'].match(/\*{3}.*\*{3}(\n|\r)?/i);
  if(matches)
    temp_driver_notes = matches.join();
  
  row['driver_notes'] = String(row['driver_notes']).replace(/\*{3}.*\*{3}(\n|\r)?/gi, '');
  
  // Test for MPU
  if(!isNumber(row['gift']) || String(row['driver_input']).match(/MPU/gi)) {
    var mpu = [
      '',
      errors,
      row['account_num'],
      date,
      row['blocks'],
      '',
      row['name_or_address'],
      '',
      driver,
      row['driver_input'] + '\n' + temp_driver_notes,
      row['driver_notes'],
      row['neighborhood'],
      row['status'],
      row['office_notes'],
    ];
    
    this.mpus.push(mpu);
    Logger.log('MPU: ' + JSON.stringify(mpu));
    return errors;
  }
  
  // Is a gift. Update Next Pickup, Status, clear Notes
  
  var next_pickup = this.getNextPickup(row['blocks']);  
  
  if(row['status'] == 'Dropoff')
    row['status'] = 'Active';
  else if(row['status'] == 'Cancelling') {
    row['status'] = 'Cancelled';
    row['blocks'] = '';
  }
  else if(row['status'] == 'Call-in' || row['status'] == 'One-time')
    row['blocks'] = '';

  // Test for RFU
  if(String(row['driver_input']).match(/RFU/gi) || row['status'] == 'Cancelling') {
    var rfu = [
      '',
      '',
      row['account_num'],
      date,
      row['blocks'],
      this.getNextPickup(row['blocks']),
      row['name_or_address'],
      row['gift'],
      driver,
      row['driver_input'] + '\n' + temp_driver_notes,
      row['driver_notes'],
      row['neighborhood'],
      row['status'],
      row['office_notes']
    ]; 
    
    this.rfus.push(rfu);
  }
  
  // Must be Gift by default
  if(isNumber(row['gift'])) {
    var gift = [
      errors,
      '',
      row['account_num'],
      date,
      row['blocks'],
      this.getNextPickup(row['blocks']),
      row['name_or_address'],
      row['gift'],
      driver,
      row['driver_input'] + '\n' + temp_driver_notes,
      row['driver_notes'],
      row['neighborhood'],
      row['status'],
      row['office_notes']
    ];
    
    this.gifts.push(gift);
    return errors;
  }
}

//---------------------------------------------------------------------
RouteProcessor.prototype.archive = function(id) {
  var entered_folder = DriveApp.getFolderById(Config['gdrive_entered_folder_id']);
  var routed_folder = DriveApp.getFolderById(Config['gdrive_routed_folder_id']);
  
  var routed_files = routed_folder.getFiles();
  var found = false;
  while(!found && routed_files.hasNext()) {
    var file = routed_files.next();
  
    if(file.getId() == id) {
      found = true;
      
      entered_folder.addFile(file);
      routed_folder.removeFile(file);
    }
  }
  if(!found)
    Logger.log("Could not find file id '%s' to archive to Entered folder.", id);
}

//---------------------------------------------------------------------
function processRouteEntries() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Routes');
  var data = sheet.getDataRange().getValues();
  var headers = data[0];
  var entries = data.slice(1);
  var now = new Date(); 
  var request_id = now.getTime();
  
  var payload = {
    'request_id': request_id,
    'entries': []
  };
  
  for(var i=0; i < entries.length; i++) { 
    var entry = entries[i];
        
    if(entry[headers.indexOf('Upload Status')])
      continue;
    else
      entry[headers.indexOf('Upload Status')] = '...';
      
    payload['entries'].push({
      'account_number': entry[headers.indexOf('Account Number')],
      'row': i+2,
      'udf': { 
        'Status': entry[headers.indexOf('Status')],
        'Neighborhood': entry[headers.indexOf('Neighborhood')],
        'Block': entry[headers.indexOf('Block')],
        'Driver Notes':  entry[headers.indexOf('Driver Notes')],
        'Office Notes':  entry[headers.indexOf('Office Notes')],
        'Next Pickup Date': date_to_ddmmyyyy(entry[headers.indexOf('Next Pickup Date')])
      },
      'gift': {
        'amount': entry[headers.indexOf('Gift Estimate')],
        'fund': Config['etap_gift_fund'],
        'campaign': Config['etap_gift_campaign'],
        'approach': Config['etap_gift_approach'],
        'date': date_to_ddmmyyyy(entry[headers.indexOf('Date')]),
        'note': 
          'Driver: ' + entry[headers.indexOf('Driver')] + '\n' + 
          entry[headers.indexOf('Driver Input')]
      }
    });
  }
  
  var ui = SpreadsheetApp.getUi();
  if(ui.alert(
    'Please confirm',
    payload['entries'].length + ' entries to upload. Go ahead?',
     ui.ButtonSet.YES_NO) == ui.Button.NO)
  return false;
  
  var trigger = ScriptApp.newTrigger('job_monitor')
  .timeBased()
  .everyMinutes(1)
  .create();
  
  var job_info = {
    'request_id': request_id,
    'script_name': 'process_route_entries',
    'sheet_name': 'Routes',
    'status_column': headers.indexOf('Upload Status') + 1,
    'trigger_id': trigger.getUniqueId(),
    'trigger_frequency': 1,
    'task':{
      'start_row': payload['entries'][0]['row'],
      'end_row': payload['entries'][payload['entries'].length-1]['row']
    }
  }
  
  set_property('job_info', JSON.stringify(job_info));
  sheet.getDataRange().setValues(data);
  
  log('process_route_entries job for ' + payload['entries'].length + ' accounts. request_id='+request_id, true); 
  
  bravoPOST(Config['etap_api_url'], 'process_route_entries', payload);
}

//---------------------------------------------------------------------
function sendReceipts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Routes');
  var ui = SpreadsheetApp.getUi();
  var rows = sheet.getDataRange().getValues();
  var headers = rows[0];
  var entries = rows.slice(1);
  
  var data = [];
  
  for(var i=0; i<entries.length; i++) {
    var entry = entries[i];
    
    if(!entry[headers.indexOf('Upload Status')] || entry[headers.indexOf('Email Status')])
      continue;
    
    data.push({
      "account_number": entry[headers.indexOf("Account Number")],
      "date": entry[headers.indexOf("Date")],
      "amount": entry[headers.indexOf("Gift Estimate")],
      "next_pickup": entry[headers.indexOf("Next Pickup Date")],
      "status": entry[headers.indexOf("Status")],
      "from": {
        "row": i+2,
        "upload_status": entry[headers.indexOf('Upload Status')],
        "worksheet": "Routes"
      }
    });
  }
  
  var options = {
    "muteHttpExceptions": true,
    "method" : 'post',
    "headers" : {
      "Authorization": "Basic " + Utilities.base64Encode(Config['bravo_auth_key'])
    },
    "payload" : {
      "keys": JSON.stringify({
        "association_name": Config['association_name'],
        "etap_endpoint": Config['etap_endpoint'],
        "etap_user": Config['etap_user'],
        "etap_pass": Config['etap_pass']
      }),
      "data": JSON.stringify(data)
    }
  };
  
  var response = UrlFetchApp.fetch(Config['server_url'] + '/receipts/process', options);
}