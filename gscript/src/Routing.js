function Routing() {}

//---------------------------------------------------------------------
Routing.buildScheduledRoutes = function(calendar_id, routed_folder_id, template_id, date, start_address, depots) {
  var job_ids = Routing.submitJobs(calendar_id, date, start_address, depots);
  
  var all_done = false;
  
  var routed_folder = DriveApp.getFolderById(routed_folder_id);
  
  /* TODO: Add a timeout length */
  
  while(!all_done) {
    for(var block in job_ids) {
      if(Routing.isComplete(job_ids[block])) {
        var r = Routing.buildSheet(job_ids[block], date, block, routed_folder, template_id);
        
        if(r)
          delete job_ids[block];     
      } 
    }
    
    if(Object.keys(job_ids).length == 0)
      all_done = true;
    else {
      Logger.log(Object.keys(job_ids).length + " routes left to build. Sleeping...");
      Utilities.sleep(5000);
    }
  }
}

//---------------------------------------------------------------------
Routing.isComplete = function(job_id) {
  try {
    var url = "https://api.routific.com/jobs/" + job_id;
    var r = UrlFetchApp.fetch(url, {'method':'get'});
  }
  catch(e) {
    Logger.log(e.name + ': ' + e.message);
    return false;
  }
  
  var solution = JSON.parse(r.getContentText());
  
  if(solution['status'] == 'finished')
    return true;
  
  return false;
}

//---------------------------------------------------------------------
Routing.buildSheet = function(job_id, date, block, routed_folder, template_id) {  
  try {
    var url = "http://www.bravoweb.ca/routing/get_route/" + job_id;
    var r = UrlFetchApp.fetch(url, {'method':'get'});
  }
  catch(e) {
    Logger.log(e.name + ': ' + e.message);
    return false;
  }
  
  var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
 //  var routed_folder = DriveApp.getFolderById(routed_folder);
  var route_template = DriveApp.getFileById(template_id);
  
  var route_title = months[date.getMonth()] + ' ' + date.getDate() + ': ' + block;
          
  // Build empty Route Template in Routed folder
  var file = route_template.makeCopy(route_title, routed_folder);
  
  var orders = JSON.parse(r.getContentText());  
    
  if(!Routing.writeToSheet(file, orders))
    return false;
    
  Logger.log('Route created for Block ' + block);
  
  return true;
}

//---------------------------------------------------------------------
Routing.submitJobs = function(calendar_id, date, start_address, depots) {
  /* Pull eTapestry data from all Residential/Business runs scheduled for
     specified date and submit to Bravo */
  
  var later = new Date(date.getTime() + (1000 * 3600 * 1));
  
  var res_events = Calendar.Events.list(calendar_id, {
    timeMin: date.toISOString(),
    timeMax: later.toISOString(),
    singleEvents: true,
    orderBy: 'startTime',
  });
  
  var job_ids = {};
  
  for(var i=0; i < res_events.items.length; i++) {
    var event = res_events.items[i];
    var block = Parser.getBlockFromTitle(event.summary);
    
    var depot = Routing.lookupDepot(
        event.description, 
        block, 
        event.location.split(","),
        depots
      );
    
    if(!depot) {
      Logger.log('Error: Could not identify depot for Block ' + block + 
          '. Could not send to Bravo for routing. Try specifying the depot name ' +
          'in the Google Calendar event description: "Depot: Strathcona"');
      continue;
    }
    
    var job_id = Routing.submitJob(block, 'driver', date, start_address, depot['location']);
    
    job_ids[block] = job_id;
  }
  
  Logger.log("job_ids: " + job_ids);
  
  return job_ids;
}


//----------------------------------------------------------------------------
Routing.lookupDepot = function(event_desc, block, postal_codes, depots) {
  /* 3 different ways of looking up depot: explicitly in calendar event description,
   * defined by Block in Config, or defined by postal code in Config
   */
  
  // Vecova (single depot)
  if(Object.keys(depots).length == 1) {
    return depots[Object.keys(depots)[0]];
  }
      
  // A. Is the depot defined explicitly in Calendar Event description?
  
  if(event_desc) {
    for(var key in depots) {
      if(event_desc.indexOf(depots[key]['name'] > -1))
        return depots[key]
    }
  }
  
  // B. Does any depot definition explicitly include this Block?
  
  for(var key in depots) {
    if(!('blocks' in depots[key]))
      continue;
        
    if(depots[key]['blocks'].indexOf(block) > -1)
      return depots[key];
  }
  
  // C. Last resort: lookup depot by postal code
  for(var i=0; i<postal_codes.length; i++) {
    if(depots['univer']['postal'].indexOf(postal_codes[i]) > -1)
      return depots['univer'];
    else if(depots['fir street']['postal'].indexOf(postal_codes[i]) > -1)
      return depots['fir street'];
    else
      return depots['strathcona'];
  }
  
  return false;
}

//----------------------------------------------------------------------------
Routing.submitJob = function(block, driver, date, start_address, end_address) {
  /* Returns: job_id for long-running Routific process */
  
  try {
    var r = UrlFetchApp.fetch(
      "http://www.bravoweb.ca/routing/start_job", {
        'method' : 'post',
        'payload' : {
          'block': block,
          'driver': driver,
          'date': date.toDateString(),
          'start_address': start_address,
          'end_address': end_address
        }
      }
    );
  }
  catch(e) {
    Logger.log(e.name + ': ' + e.message);
    return false;
  }
  
  Logger.log("submitJob returning job_id '%s'", r.getContentText());
  
  return r.getContentText();
}


//----------------------------------------------------------------------------
Routing.writeToSheet = function(file, data) {
  /* Write sorted orders to the given Route sheet
     Add all formulas and formatting */
   
  Logger.log('%s stops', data.length);
  
  var rows = [];
  
  // Delete first Office stop
  data = data.slice(1, data.length);
  
  var ss = SpreadsheetApp.open(file);
  var sheet = ss.getSheetByName("Route");
  var headers = ss.getSheetByName('Route').getRange('1:1').getValues()[0];
  
  for(var i=0; i<data.length; i++) {
    if(i == data.length - 1) {
      rows[i] = ['', '', '', 'Name: Depot', '', '', '', '', '', ''];
      continue;
    }
    
    var order = data[i];
    
    /* Info Column format (column #5):
    
    Notes: Fri Apr 22 2016: Pickup Needed
    
    Name: Cindy Borsje
    Neighborhood: Lee Ridge
    Block: R10Q,R8R
    Contact (business only): James Schmidt
    Phone: 780-123-4567
    Email: Yes/No
    
    */
    
    var info = '';
    
    if(order['customNotes']['driver notes']) {
      info += 'NOTE: ' + order['customNotes']['driver notes'] + '\n\n';
      
      //route.headers.indexOf('Order Info')+1
      sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontWeight("bold");
      
      if(order['customNotes']['driver notes'].indexOf('***') > -1) {
        info = info.replace(/\*\*\*/g, '');
        sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontColor("red");
      }
    }
    
    info += 'Name: ' + order['customNotes']['name'] + '\n';
    
    if(order['customNotes']['neighborhood'])
      info += 'Neighborhood: ' + order['customNotes']['neighborhood'] + '\n';
    
    info += 'Block: ' + order['customNotes']['block'];
    
    if(order['customNotes']['contact'])
      info += '\nContact: ' + order['customNotes']['contact'];
    
    if(order['customNotes']['phone'])
      info += '\nPhone: ' + order['customNotes']['phone'];
    
    if(order['customNotes']['email'])
      info += '\nEmail: ' + order['customNotes']['email'];
    
    rows[i] = [
      order['gmaps_url'] || '',
      '',
      '',   
      info,
      order['customNotes']['id'] || '',
      order['customNotes']['driver notes'] || '',
      order['customNotes']['block'] || '',
      order['customNotes']['neighborhood'] || '',
      order['customNotes']['status'] || '',
      order['customNotes']['office notes'] || ''
    ];
  }
  
  // Start on Row 2, preserve headers
  sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  
  // Write Google Maps URL formulas
  
  var formulas = [];
  
  for(var i=0; i<data.length; i++) {
    var order = data[i];
    
    var address_components = order['location_name'].split(', ');
    
    // Remove Postal Code from Google Maps URL label
    if(Parser.isPostalCode(address_components[address_components.length-1]))
       address_components.pop();  
 
    formulas[i] = [
      '=HYPERLINK("' + order['gmaps_url'] + '","' + address_components.join(', ') + '")'
    ];
    Logger.log(formulas[i]);
  }
  
  var addressRange = sheet.getRange(2, 1, formulas.length, 1);
  
  addressRange.setFormulas(formulas);
  addressRange.setVerticalAlignment("middle");
  addressRange.setHorizontalAlignment("center");
  
  // Hide unused rows
  var a = sheet.getRange("A:$A").getValues().join("//").split("//");
  var hide_start = 1 + rows.length + 1;
  var hide_end = a.indexOf("***Route Info***");
  sheet.deleteRows(hide_start, hide_end - hide_start + 1);
  
  return true;
}