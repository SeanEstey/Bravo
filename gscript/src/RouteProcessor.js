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
RouteProcessor.prototype.import = function(route) {
  /* Updates all stops then writes them to appropriate GiftEntry sheets */
  
  this.gifts = [];
  this.rfus = [];
  this.mpus = [];
  this.errors = [];
  
  this.getPickupDates(route);
  
  // Process all Gifts, MPU's, No Pickups, etc
  
  for(var i=0; i<route.orders.length; i++) {
    try {  
      var res = this.processRow(route, i);
      
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
RouteProcessor.prototype.getPickupDates = function(route) {
  /* Build a dictionary of all blocks referenced in the route with their
   * next pickup date: {'R3C': 'September 9, 2015', 'B4A': 'Dec 20, 2016'}
   * Returns: dict obj on success, false on error finding >= 1 dates
   */
  
  this.pickup_dates = {};
  
  var fails = [];
    
  for(var i=0; i<route.orders.length; i++) {
    var blocks = route.getValue(i,'Block')
    blocks = blocks.split(', ');
    
    for(var j=0; j<blocks.length; j++) {
      if(!this.pickup_dates.hasOwnProperty(blocks[j])) {
        var next_block = Schedule.findBlock(blocks[j], this.events);
        
        if(!next_block) {
          if(fails.indexOf(blocks[j]) < 0)
            fails.push(blocks[j]);
        }
        
        this.pickup_dates[blocks[j]] = next_block.date;
      }
    }
  }
  
  if(fails.length > 0) {
    Logger.log("Failed to find NPD's for blocks: %s", fails.toString());
    return false;
  }
  
  return true;
}

//---------------------------------------------------------------------
RouteProcessor.prototype.getNextPickup = function(blocks) {
  /* Find the soonest pickup from list of blocks
   * @blocks: string of comma separated blocks
   * Returns: Date object
   */

  if(!blocks)
    return false;
  
  var dates = [];
  blocks = blocks.split(',');
  
  for(var i=0; i<blocks.length; i++) {
    if(this.pickup_dates.hasOwnProperty(blocks[i]))
      dates.push(this.pickup_dates[blocks[i]]);
  }
  
  if(dates.length == 0)
    return false;
    
  // Sort chronologically.
  dates.sort(function(a, b) {
    return a.getTime() - b.getTime();
  });
  
  // Return earliest date
  return dates[0];
}


//---------------------------------------------------------------------
RouteProcessor.prototype.processRow = function(route, order_idx) { 
  /* Process a line entry from a route
   * Returns: string if data contains any errors, true otherwise
   */
  
  /*** Test for invalid data ***/
  
  var row = route.orderToDict(order_idx);
  
  var errors = '';
  
  if(!isNumber(row['Account Number']))
    errors += 'Stop #' + String(order_idx+1) + ': Invalid Account #';
  
  if(!row['Block'] || !Parser.isBlockList(row['Block']))
    errors += 'Stop #' + String(order_idx+1) + ': Missing or invalid Blocks';
  
  if(!row['Status'])
    errors += 'Stop #' + String(order_idx+1) + ': Missing Status';
  
  // Remove unecessary newlines or spaces
  row['Driver Notes'] = String(row['Driver Notes']).trim();
  row['Office Notes'] = String(row['Office Notes']).trim();
  row['Driver Input'] = String(row['Driver Input']).trim();
  
  /*** Now process ***/
  
  // Remove any necessary blocks from note with format: "***RMV R2P***"
  var matches = String(row['Office Notes']).match(/\*{3}RMV\s(B|R)\d{1,2}[a-zA-Z]{1}\*{3}(\n|\r)?/g);
  
  if(matches) {
    for(var i=0; i<matches.length; i++) {
      var rmv_note = matches[i];
      var rmv_block = rmv_note.match(/(B|R)\d{1,2}[a-zA-Z]/g)[0];
      var block_list = row['Block'].split(',');
      
      for(var j=0; j<block_list.length; j++) {
        if(block_list[j] == rmv_block)
          block_list.splice(j, 1);
      }
      row['Block'] = block_list.join(',');
      row['Office Notes'] = row['Office Notes'].replace(rmv_note, '');
    }
  }
  
  // Clear any temporary Driver Notes surrounded by a set of '***' characters
  var temp_driver_notes = "";
  var matches = row['Driver Notes'].match(/\*{3}.*\*{3}(\n|\r)?/i);
  if(matches)
    temp_driver_notes = matches.join();
  
  row['Driver Notes'] = String(row['Driver Notes']).replace(/\*{3}.*\*{3}(\n|\r)?/gi, '');
  
  // Test for MPU
  if(!isNumber(row['Gift Estimate']) || String(row['Driver Input']).match(/MPU/gi)) {
    
    var mpu_headers = this.sheets['MPU'].getDataRange("1:1").getValues()[0];
    var mpu = [];
    
    for(var header in mpu_headers) {
      if(row[header])
        mpu.push(row[header]);
      else
        mpu.push('');      
    }
  
    mpu[mpu_headers.indexOf('Date')] = route.date;
    mpu[mpu_headers.indexOf('Driver')] = route.driver;
    mpu[mpu_headers.indexOf('Request Note')] = row['Driver Input'] + '\n' + temp_driver_notes;
    
    this.mpus.push(mpu);
  
    Logger.log('MPU: ' + JSON.stringify(mpu));
    
    return errors;
  }
  
  // Is a gift. Update Next Pickup, Status, clear Notes
  
  var next_pickup = this.getNextPickup(row['Block']);  
  
  if(row['Status'] == 'Dropoff')
    row['Status'] = 'Active';
  else if(row['Status'] == 'Cancelling') {
    row['Status'] = 'Cancelled';
    row['Block'] = '';
  }
  else if(row['Status'] == 'Call-in' || row['Status'] == 'One-time')
    row['Block'] = '';

  // Test for RFU
  if(String(row['Driver Input']).match(/RFU/gi) || row['Status'] == 'Cancelling') {
    var rfu_headers = this.sheets['RFU'].getDataRange("1:1").getValues()[0];
    var rfu = [];
    
    for(var header in rfu_headers) {
      if(row[header])
        rfu.push(row[header]);
      else
        rfu.push('');      
    }
    
    rfu[rfu_headers.indexOf('Date')] = route.date;
    rfu[rfu_headers.indexOf('Next Pickup Date')] = this.getNextPickup(row['Block']); 
    rfu[rfu_headers.indexOf('Driver')] = route.driver;
    rfu[rfu_headers.indexOf('Request Note')] = row['Driver Input'] + '\n' + temp_driver_notes;
   
    this.rfus.push(rfu);
  }
  
  // Must be Gift by default
  if(isNumber(row['Gift Estimate'])) {
    var gift_headers = this.sheets['Routes'].getDataRange("1:1").getValues()[0];
    var gift = [];
    
    for(var header in gift_headers) {
      if(row[header])
        gift.push(row[header]);
      else
        gift.push('');      
    }
    
    gift[gift_headers.indexOf('Upload Status')] = errors;
    gift[gift_headers.indexOf('Date')] = route.date;
    gift[gift_headers.indexOf('Next Pickup Date')] = this.getNextPickup(row['Block']); 
    gift[gift_headers.indexOf('Driver')] = route.driver;
    gift[rfu_headers.indexOf('Driver Input')] = row['Driver Input'] + '\n' + temp_driver_notes;
       
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