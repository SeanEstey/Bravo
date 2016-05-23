//---------------------------------------------------------------------
function RouteProcessor(ss_ids, cal_ids, folder_ids, etap_id, _events) {
  /*
   * @_events: optional. sorted list of res/bus cal events
   */
  
  this.ss_ids = ss_ids;
  this.cal_ids = cal_ids;
  this.folder_ids = folder_ids;
  this.etap_id = etap_id;
  
  var bravo_ss = SpreadsheetApp.openById(ss_ids['bravo']);
  
  this.sheets = {
    'Routes': bravo_ss.getSheetByName('Routes'),
    'RFU': bravo_ss.getSheetByName('RFU'),
    'MPU': bravo_ss.getSheetByName('MPU'), 
  };
  
  this.headers = this.sheets['Routes'].getRange(1,1,1,this.sheets['Routes'].getMaxColumns()).getValues()[0];
  
  var today = new Date();
  var tomorrow = new Date(Date.now() + (1000 * 3600 * 24));
  var one_month = new Date(Date.now() + (1000 * 3600 * 24 * 7 * 4));
  var six_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 6));
  var sixteen_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 16));
  
  if(_events == undefined) {
    var res_events = Schedule.getEventsBetween(this.cal_ids['res'], one_month, sixteen_weeks);
    var bus_events = Schedule.getEventsBetween(this.cal_ids['bus'], tomorrow, six_weeks);
    this.events = res_events.concat(bus_events);
    
    this.events.sort(function(a, b) {
      return parseDate(a.start.date).getTime() - parseDate(b.start.date).getTime();
    });
  }
  else
    this.events = _events;
  
  this.gifts = [];
  this.rfus = [];
  this.mpus = [];
  this.errors = [];
  this.pickup_dates = [];
}

//---------------------------------------------------------------------
RouteProcessor.prototype.importRoutes = function(file_ids) {
  /* Take a list of spreadsheet_id's, import the routes, update stats and inventory,
   * archive into 'Entered' folder.
   */
  
  for(var i=0; i<file_ids.length; i++) {
    var ss_id = file_ids[i];
    
    var route = new Route(ss_id);
    
    this.import(route);
    
    updateStats(this.ss_ids['stats'], this.ss_ids['stats_archive'], route);
    
    updateInventory(this.ss_ids['inventory'], route);
        
    this.archive(route.id); 
  }
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
      var order_info = route.getValue(i,'Order Info');
      var act_name_regex = /Name\:\s(([a-zA-Z]*?\s)*){1,5}/g;
      var account_name = '';
      
      // Parse Account Name from "Order Info" string
      if(act_name_regex.test(order_info))
         account_name = order_info.match(act_name_regex)[0] + '\n';    
      
      var row = {
        'account_num': route.getValue(i,'ID'),
        'name_or_address': account_name + route.getValue(i,'Address'),
        'gift': route.getValue(i,'$'),
        'driver_input': route.getValue(i,'Notes'),
        'driver_notes': route.getValue(i,'Driver Notes'),
        'blocks': route.getValue(i,'Block'),
        'neighborhood': route.getValue(i,'Neighborhood'),
        'status': route.getValue(i,'Status'),
        'office_notes': route.getValue(i,'Office Notes')
      };
      
      if(row['neighborhood'])
        row['neighborhood'] = row['neighborhood'].replace(/, /g, ',');
      
      if(row['blocks'])
        row['blocks'] = row['blocks'].replace(/, /g, ',');
      
      var res = this.processRow(row, i+1, route.date, route.driver);
      
      if(res)
        this.errors.push(res);
    }
    catch(e) {
      var msg = 
        route.title_block + ' import failed. \\n' +
        'Row ' + (i+1) + ': [' + route.orders[i].toString() + ']\\n' +
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
    var blocks = route.getValue(i,'Block')
    blocks = blocks.split(', ');
    
    for(var j=0; j<blocks.length; j++) {
      if(!this.pickup_dates.hasOwnProperty(blocks[j]))
        this.pickup_dates[blocks[j]] = Schedule.findBlock(blocks[j], this.events).date;
    }
  }
    
 // Logger.log('pickup_dates: ' + JSON.stringify(this.pickup_dates));
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
RouteProcessor.prototype.processRow = function(row, row_num, date, driver) { 
  /* Process a line entry from a route
   * Returns non-empty string if error(s) found, nothing otherwise
   */
  
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
  var entered_folder = DriveApp.getFolderById(this.folder_ids['entered']);
  var routed_folder = DriveApp.getFolderById(this.folder_ids['routed']);
  
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
RouteProcessor.prototype.uploadEntries = function() {
  var entries = this.sheets['Routes'].getDataRange().getValues().slice(1);
  
  var request_id = new Date().getTime();
  
  var payload = {
    'request_id': request_id,
    'entries': []
  };
  
  for(var i=0; i < entries.length; i++) { 
    var entry = entries[i];
        
    if(entry[this.headers.indexOf('Upload Status')])
      continue;
    else
      entry[this.headers.indexOf('Upload Status')] = '...';
      
    payload['entries'].push({
      'account_number': entry[this.headers.indexOf('Account Number')],
      'row': i+2,
      'udf': { 
        'Status': entry[this.headers.indexOf('Status')],
        'Neighborhood': entry[this.headers.indexOf('Neighborhood')],
        'Block': entry[this.headers.indexOf('Block')],
        'Driver Notes':  entry[this.headers.indexOf('Driver Notes')],
        'Office Notes':  entry[this.headers.indexOf('Office Notes')],
        'Next Pickup Date': date_to_ddmmyyyy(entry[this.headers.indexOf('Next Pickup Date')])
      },
      'gift': {
        'amount': entry[this.headers.indexOf('Gift Estimate')],
        'fund': this.etap_id['fund'],
        'campaign': this.etap_id['campaign'],
        'approach': this.etap_id['approach'],
        'date': date_to_ddmmyyyy(entry[this.headers.indexOf('Date')]),
        'note': 
          'Driver: ' + entry[this.headers.indexOf('Driver')] + '\n' + 
          entry[this.headers.indexOf('Driver Input')]
      }
    });
  }
  
  var ui = SpreadsheetApp.getUi();

  if(ui.alert(
    'Please confirm',
    payload['entries'].length + ' entries to upload. Go ahead?',
     ui.ButtonSet.YES_NO) == ui.Button.NO)
  return false;

  return payload;
}


//---------------------------------------------------------------------
RouteProcessor.prototype.sendReceipts = function() {
  var entries = this.sheets['Routes'].getDataRange().getValues().slice(1);
  
  for(var i=0; i<entries.length; i++) {
    var entry = entries[i];
    
    if(!entry[this.headers.indexOf('Upload Status')] || entry[this.headers.indexOf('Email Status')])
      continue;
    
    data.push({
      "account_number": entry[this.headers.indexOf("Account Number")],
      "date": entry[this.headers.indexOf("Date")],
      "amount": entry[this.headers.indexOf("Gift Estimate")],
      "next_pickup": entry[this.headers.indexOf("Next Pickup Date")],
      "status": entry[this.headers.indexOf("Status")],
      "from": {
        "row": i+2,
        "upload_status": entry[this.headers.indexOf('Upload Status')],
        "worksheet": "Routes"
      }
    });
  }
  
  var options = {
    "muteHttpExceptions": true,
    "method" : 'post',
    "headers" : {
      "Authorization": "Basic " + Utilities.base64Encode(Settings['bravo_auth_key'])
    },
    "payload" : {
      "keys": JSON.stringify({
        "association_name": this.etap_id['association'],
        "etap_endpoint": this.etap_id['endpoint'],
        "etap_user": this.etap_id['user'],
        "etap_pass": this.etap_id['pw']
      }),
      "data": JSON.stringify(data)
    }
  };
  
  var response = UrlFetchApp.fetch(BRAVO_URL + '/receipts/process', options);
}