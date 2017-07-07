//---------------------------------------------------------------------
function RouteManager(conf) {
  /* @_events: optional. sorted list of res/bus cal events
   */
  
  this.pickup_dates = [];
  this.conf = conf;
  this.bravo_ss = SpreadsheetApp.openById(conf['BRAVO_SS_ID']);
  this.don_wks = this.bravo_ss.getSheetByName("Donations");
  this.don_hdr = this.don_wks.getRange(1,1,1,this.don_wks.getMaxColumns()).getValues()[0];
  this.iss_wks = this.bravo_ss.getSheetByName("Issues");
  this.maps = API(
    '/maps/get',
    conf);
  
  this.events = Schedule.getEventsBetween(
    conf['CAL_IDS']['RES'],
    new Date(Date.now() + WEEK_MS * 4),
    new Date(Date.now() + WEEK_MS * 16));
  
  if(conf['CAL_IDS'].hasOwnProperty('BUS')) {
    this.events = this.events.concat(
      Schedule.getEventsBetween(
        conf['CAL_IDS']['BUS'],
        new Date(Date.now() + DAY_MS),
        new Date(Date.now() + WEEK_MS * 6)));
  }
  
  this.events.sort(function(a, b) {
    return parseDate(a.start.date).getTime() - parseDate(b.start.date).getTime();
  });
}

//---------------------------------------------------------------------
RouteManager.prototype.importRoutes = function(file_ids) {
  /* Take a list of spreadsheet_id's, import the routes, update stats and inventory,
   * archive into 'Entered' folder.
   */
  
  var stats_mgr = new StatsManager(this.conf);
  
  for(var i=0; i<file_ids.length; i++) {
    var ss_id = file_ids[i]; 
    var route = new Route(this.conf['AGCY'], ss_id);
    this.import(route); 
    stats_mgr.writeStats(route);
    stats_mgr.writeInventory(route); 
    this.archive(route.ss_id); 
  }
}

//---------------------------------------------------------------------
RouteManager.prototype.import = function(route, ui) {
  /* Updates all stops then writes them to appropriate GiftEntry sheets 
   * @ui: optional UI to display MsgBox
   * @route: Route object
   */
  
  var donations = [];
  var issues = [];
  var errors = [];
  this.getPickupDates(route);
  
  // Process Donations and Issues
  
  for(var i=0; i<route.orders.length; i++) {
    try {  
      var results = this.processRow(route, i);
      
      for(var j in results) {
        if(results[j]['sheet'] == 'Donations')
          donations.push(results[j]['row']);
        else if(results[j]['sheet'] == 'Issues')
          issues.push(results[j]['row']); 
        if(results[j]['row'][0])
          errors.push(results[j]['row'][0]);
      }
    }
    catch(e) {
      var msg = 
        route.properties['Block'] + ' import failed. \\n' +
        'Row ' + (i+1) + ': [' + route.orders[i].toString() + ']\\n' +
        'Msg: ' + e.message + '\\n' +
        'File: ' + e.fileName + '\\n' + 
        'Line: ' + e.lineNumber;    
  
      this.bravo_ss.toast(msg);
      Logger.log(msg);
    }
  }
  
  appendRowsToSheet(this.don_wks, donations, 1);
  appendRowsToSheet(this.iss_wks, issues, 1);
  
  var iss_hdr = this.iss_wks.getRange(
    1,
    1,
    this.iss_wks.getMaxRows(),
    this.iss_wks.getMaxColumns())
  .getValues()[0];
  
  for(var i=0; i<issues.length; i++) {
    var row = this.iss_wks.getMaxRows() - issues.length + i + 1;
    
    this.iss_wks.getRange(row, iss_hdr.indexOf('Description')+1,1,1)
      .setNote(issues[i][iss_hdr.indexOf('Description')]);
    this.iss_wks.getRange(row, iss_hdr.indexOf('Driver Notes')+1,1,1)
      .setNote(issues[i][iss_hdr.indexOf('Driver Notes')]);
    this.iss_wks.getRange(row, iss_hdr.indexOf('Office Notes')+1,1,1)
      .setNote(issues[i][iss_hdr.indexOf('Office Notes')]);
  }
   
  for(var i=0; i<donations.length; i++) {
    var row = this.don_wks.getMaxRows() - donations.length + i + 1;
    
    this.don_wks.getRange(row, this.don_hdr.indexOf('Notes')+1,1,1)
      .setNote(donations[i][this.don_hdr.indexOf('Notes')]);
    this.don_wks.getRange(row, this.don_hdr.indexOf('Driver Notes')+1,1,1)
      .setNote(donations[i][this.don_hdr.indexOf('Driver Notes')]);
    this.don_wks.getRange(row, this.don_hdr.indexOf('Office Notes')+1,1,1)
      .setNote(donations[i][this.don_hdr.indexOf('Office Notes')]);
  }
  
  // Print Import Summary
  
  var summary_msg = 
    route.properties['Block'] + ' import complete.\\n' +
    'Donations: ' + String(donations.length) + '\\n' +
    'Issues: ' + String(issues.length);   
      
  if(errors.length > 0)
    summary_msg += '\\nErrors: ' + errors;
  
  Logger.log('summary_msg: ' + summary_msg);
  this.bravo_ss.toast(summary_msg);
  return true;
}

//---------------------------------------------------------------------
RouteManager.prototype.getPickupDates = function(route) {
  /* Build a dictionary of all blocks referenced in the route with their
   * next pickup date: {'R3C': 'September 9, 2015', 'B4A': 'Dec 20, 2016'}
   * Returns: dict obj on success, false on error finding >= 1 dates
   */
  
  this.pickup_dates = {};
  var fails = [];
    
  for(var i=0; i<route.orders.length; i++) {
    var blocks = route.getOrderValue(i,'Block');
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
RouteManager.prototype.getNextPickup = function(blocks) {
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
RouteManager.prototype.processRow = function(route, order_idx) { 
  /* Process a single order (row) from a route
   * Returns: [{'sheet': 'dest_sheet_name', 'row': [column_values]}, ...], one element
   * for each needed worksheet row
   */
      
  var order = route.orderToDict(order_idx);
  var errors = '';
  var results = [];
  
  if(!isNumber(order['ID']))
    errors += 'Stop #' + String(order_idx+1) + ': Invalid Account #';  
  if(!order['Block'] || !Parser.isBlockList(order['Block']))
    errors += 'Stop #' + String(order_idx+1) + ': Missing or invalid Blocks';
  if(!order['Status'])
    errors += 'Stop #' + String(order_idx+1) + ': Missing Status';
  
  // Remove unecessary newlines or spaces
  if(order['Driver Notes']) {
    order['Driver Notes'] = String(order['Driver Notes']).trim();
    order['Office Notes'] = String(order['Office Notes']).trim();
    order['Notes'] = String(order['Notes']).trim();
  }
  
  /*** Now process ***/
  
  // Remove any necessary blocks from note with format: ***RMV R2P -GR***
  if(order['Office Notes'])
    var matches = String(order['Office Notes']).match(/\*{3}RMV\s(B|R)\d{1,2}\w(.+)?\*{3}(\n|\r)?/g);
  
  if(matches) {
    for(var i=0; i<matches.length; i++) {
      var rmv_note = matches[i];
      var rmv_block = rmv_note.match(/(B|R)\d{1,2}\w/g)[0];
      var block_list = order['Block'].split(',');
      
      for(var j=0; j<block_list.length; j++) {
        if(block_list[j] == rmv_block)
          block_list.splice(j, 1);
      }
      order['Block'] = block_list.join(',');
      order['Office Notes'] = order['Office Notes'].replace(rmv_note, '');
    }
  }
   
  // Clear temp notes
  var temp = "";
  if(order['Driver Notes']) {
    var matches = order['Driver Notes'].match(/\*{3}.*\*{3}(\n|\r)?/i);  
    if(matches)
      temp = matches.join();
    order['Driver Notes'] = String(order['Driver Notes']).replace(/\*{3}.*\*{3}(\n|\r)?/gi, '');
  }
  
  var is_miss = (!isNumber(order['Estimate']) || String(order['Notes']).match(/MPU/gi));
  var is_issue = (String(order['Notes']).match(/RFU/gi) || order['Status'] == 'Cancelling');
  
  if(is_miss || is_issue) {
    var hdr = this.iss_wks.getRange("1:1").getValues()[0];
    var issue = [];
    
    for(var idx in hdr) {
      if(order[hdr[idx]])
        issue.push(order[hdr[idx]]);
      else
        issue.push('');      
    }
  
    issue[hdr.indexOf('Date')] = route.properties['Date'];
    issue[hdr.indexOf('Resolved')] = "No";
    issue[hdr.indexOf('Description')] = route.properties['Driver'] + ": \"" + order["Notes"] +"\"\n"+ temp;
    issue[hdr.indexOf('Next Pickup')] = this.getNextPickup(order['Block']);
    issue[hdr.indexOf('Type')] = (is_miss ? "Missed" : "Followup");    
    results.push({'sheet': 'Issues', 'row': issue}); 
  }
      
  // Process Donation
  if(isNumber(order['Estimate'])) {   
    if(order['Status'] == 'Dropoff')
      order['Status'] = 'Active';
    else if(order['Status'] == 'Cancelling') {
      order['Status'] = 'Cancelled';
      order['Block'] = '';
    }
    else if(order['Status'] == 'Call-in' || order['Status'] == 'One-time') {
      order['Block'] = '';
    }
    
    var donation = [];
    var hdr = this.don_hdr;
    
    for(var idx in hdr) {
      if(order[hdr[idx]])
        donation.push(order[hdr[idx]]);
      else
        donation.push('');      
    }
    
    donation[hdr.indexOf('Estimate')] = Number(order['Estimate']);
    donation[hdr.indexOf('Date')] = route.properties['Date'];
    donation[hdr.indexOf('Next Pickup')] = this.getNextPickup(order['Block']) || ''; 
    donation[hdr.indexOf('Driver')] = route.properties['Driver'];
    donation[hdr.indexOf('Notes')] = order['Notes'] + '\n' + temp;
    donation[0] += errors;
    results.push({'sheet': 'Donations', 'row': donation});
  }
  
  return results;
}

//---------------------------------------------------------------------
RouteManager.prototype.validate = function() {
  return;
  
  /*
  // Verify Address of Residential account is matched with correct geographical Block 
  if(Parser.isRes(route.block)) {
    try {
      var response = Maps.newGeocoder().geocode(order['Address']);
    }
    catch(e) {
      Logger.log('geocode failed: ' + e.msg);
      return false;
    }
    
    order['Validation'] = '';
    
    // Add neighborhood name into Validation column
    
    var neighborhoods = [];
    
    var partial_match = false;
    
    var num_rows = this.don_wks.getMaxRows();
    
    for(var i in response['results']) {
      var addresses = response['results'][i]['address_components'];
      
      if('partial_match' in response['results'][i]) {
        partial_match = true;
        order['Validation'] += "Address not fully resolved. See Note.\n\n";
      }
      
      for(var j=0; j<addresses.length; j++) {
        if(addresses[j]['types'].indexOf('neighborhood') > -1)
          if(neighborhoods.indexOf(addresses[j]['long_name']) == -1)
             neighborhoods.push(addresses[j]['long_name']);
      }
    }
    
    if(!partial_match)
      order['Validation'] += "Address OK\n";
    
    if(neighborhoods.length > 0)
      order['Validation'] += "Neighborhood: \"" + neighborhoods.join('\",\"') + '\"\n';
    
        
    // Match address coordinates to map data and find Block
    
    if(response['results'].length == 0)
      order['Validation'] += "Could not verify address\n"; 
    
    // NOTE: Only searching through first result. May not be correct result.
    if(response['results'].length == 1 && !('partial_match' in response.results[0])) {               
      var map_title = Geo.findMapTitle(
        response['results'][0]['geometry']['location']['lat'],
        response['results'][0]['geometry']['location']['lng'],
        this.maps);
      
      if(map_title) {
        var block = Parser.getBlockFromTitle(map_title);
        
        if(order['Block'] != block) {
          Logger.info('Block mismatch');
          
          order['Validation'] += 'Block mismatch. Belongs to ' + map_title;
        }
        else
          order['Validation'] += 'Block OK';
      }
      else
        order['Validation'] += 'Block map not found';
    } 
  }
  */
}

//---------------------------------------------------------------------
RouteManager.prototype.archive = function(ss_id) {
  var entered_folder = DriveApp.getFolderById(this.conf['ENTRD_FDR_ID']);
  var routed_folder = DriveApp.getFolderById(this.conf['ROUTED_FDR_ID']);
  
  var routed_files = routed_folder.getFiles();
  var found = false;
  while(!found && routed_files.hasNext()) {
    var file = routed_files.next();
  
    if(file.getId() == ss_id) {
      found = true;
      
      entered_folder.addFile(file);
      routed_folder.removeFile(file);
    }
  }
  if(!found)
    Logger.log("Could not find file id '%s' to archive to Entered folder.", ss_id);
}

//---------------------------------------------------------------------
RouteManager.prototype.buildEntriesPayload = function(ui) {
  /* Prepare entries on "Routes" sheet for update/upload to eTapestry via
   * Bravo server
   * @ui: optional arg to display confirmation Dialog
   * Returns: payload array
   */
  
  var entries = this.don_wks.getDataRange().getValues().slice(1);
  var status = this.don_wks.getRange("B2:B").getValues();
  var request_id = new Date().getTime();
  var payload = [];
  var req_fields = ['Date', 'ID', 'Status'];
  
  for(var i=0; i < entries.length; i++) { 
    var entry = entries[i];
        
    if(entry[this.don_hdr.indexOf('Upload')])
      continue;
    else
      status[i][0] = '...';
    
    var err = null;
    for(var j=0; j<req_fields.length; j++) {
      var field = req_fields[j];
      if(!entry[this.don_hdr.indexOf(field)]) {
        status[i][0] = "Missing field " + field;
        err = true;
      }
    }
    
    if(err)
      continue;
      
    payload.push({
      'acct_id': entry[this.don_hdr.indexOf('ID')],
      'ss_row': i+2,
      'udf': { 
        'Status': entry[this.don_hdr.indexOf('Status')],
        'Neighborhood': entry[this.don_hdr.indexOf('Neighborhood')],
        'Block': entry[this.don_hdr.indexOf('Block')],
        'Driver Notes':  entry[this.don_hdr.indexOf('Driver Notes')],
        'Office Notes':  entry[this.don_hdr.indexOf('Office Notes')],
        'Next Pickup Date': date_to_ddmmyyyy(entry[this.don_hdr.indexOf('Next Pickup')])
      },
      'gift': {
        'amount': entry[this.don_hdr.indexOf('Estimate')],
        'fund': this.conf['ETAP_FUND'],
        'campaign': this.conf['ETAP_CAMPAIGN'],
        'approach': this.conf['ETAP_APPROACH'],
        'date': date_to_ddmmyyyy(entry[this.don_hdr.indexOf('Date')]),
        'note': 
          'Driver: ' + entry[this.don_hdr.indexOf('Driver')] + '\n' + 
          entry[this.don_hdr.indexOf('Notes')]
      }
    });
  }
  
  if(ui != undefined) {    
    if(ui.alert(
      'Please confirm',
      payload.length + ' entries to upload. Go ahead?',
      ui.ButtonSet.YES_NO) == ui.Button.NO)
      return false;
  }

  var data = [this.don_hdr].concat(entries);
  this.don_wks.getRange("B2:B").setValues(status);
  return payload;
}

//---------------------------------------------------------------------
RouteManager.prototype.sendReceipts = function(ui) {
  
  var entries = this.don_wks.getDataRange().getValues().slice(1);
  var status = this.don_wks.getRange("C2:C").getValues();
  var req_fields = ['ID', 'Date', 'Status'];
  var payload = [];
  
  for(var i=0; i<entries.length; i++) {
    var entry = entries[i];
    
    if(!entry[this.don_hdr.indexOf('Upload')] || entry[this.don_hdr.indexOf('Receipt')])
      continue;
    else
      status[i][0] = '...';
    
    var err = null;
    for(var j=0; j<req_fields.length; j++) {
      var field = req_fields[j];
      if(!entry[this.don_hdr.indexOf(field)]) {
        status[i][0] = "Missing field " + field
        err = true;
      }
    }
    
    if(err)
      continue;
    
    payload.push({
      "acct_id": entry[this.don_hdr.indexOf("ID")],
      "date": entry[this.don_hdr.indexOf("Date")],
      "amount": entry[this.don_hdr.indexOf("Estimate")],
      "next_pickup": entry[this.don_hdr.indexOf("Next Pickup")],
      "status": entry[this.don_hdr.indexOf("Status")],
      "ss_row": i+2
    });
  }
  
  if(ui != undefined) {    
    if(ui.alert(
      'Please confirm',
      payload.length + ' entries to upload. Go ahead?',
      ui.ButtonSet.YES_NO) == ui.Button.NO)
      return false;
  }
  
  this.don_wks.getRange("C2:C").setValues(status);

  API(
    '/accounts/receipts',
    this.conf, {
      "entries":JSON.stringify(payload)});
}
