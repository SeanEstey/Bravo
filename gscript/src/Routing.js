function Routing() {}

//---------------------------------------------------------------------
Routing.buildScheduled = function(calendar_id, routed_folder, template_id, date, depots) {
  /* Pull eTapestry data from all Residential/Business runs scheduled for
     specified date and submit to Bravo */
  
  var routed_folder = DriveApp.getFolderById(routed_folder);
  var route_template = DriveApp.getFileById(template_id);
  
  var later = new Date(date.getTime() + (1000 * 3600 * 1));
  
  var res_events = Calendar.Events.list(calendar_id, {
    timeMin: date.toISOString(),
    timeMax: later.toISOString(),
    singleEvents: true,
    orderBy: 'startTime',
  });
  
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
      log('Error: Could not identify depot for Block ' + block + 
          '. Could not send to Bravo for routing. Try specifying the depot name ' +
          'in the Google Calendar event description: "Depot: Strathcona"', true);
      continue;
    }
    
    var orders = Routing.solve(
      block, 
      'driver',
      date,
      '11130 131 St NW, Edmonton, AB',
      depot['location']
    );
    
     // Build Template file in routed folder
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  
    var route_title = months[date.getMonth()] + ' ' + date.getDate() + ': ' + block;
          
    var file = route_template.makeCopy(route_title, routed_folder);
    
    Routing.writeToSheet(file, orders);
    
    log('Route created for Block ' + block, true);
  }
}

//----------------------------------------------------------------------------
Routing.lookupDepot = function(event_desc, block, postal_codes, depots) {
  /* 3 different ways of looking up depot: explicitly in calendar event description,
   * defined by Block in Config, or defined by postal code in Config
   */
      
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
Routing.solve = function(block, driver, date, start_addy, end_addy) {
  /* Get ordered stops from Bravo */
  
  try {
    var r = UrlFetchApp.fetch(
      "http://www.bravoweb.ca/routing/get_sorted_orders", {
        'method' : 'post',
        'payload' : {
          'block': block,
          'driver': driver,
          'date': date.toDateString(),
          'start_addy': start_addy,
          'end_addy': end_addy
        }
      }
    );
  }
  catch(e) {
    Logger.log('exception!');
    Logger.log(e);
    return false;
  }
  
  if(r.getResponseCode() != 200 && r.getResponseCode() != 408) {
    // Deal with errors
  }
  
  // TODO: Remove any control characters first
  
  var stops = JSON.parse(r.getContentText());
  
  Logger.log("%s stops returned", stops.length);
  
  return stops;
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
      order['customNotes']['next pickup'] || '',   // Temporary. Remove future pickups from route
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
}


// Add this in writeToSheet() for testing
//   var data = '[{"location_name": "11130 131 St NW", "location_id": "Office", "arrival_time": "08:00"}, {"customNotes": {"status": "Active", "neighborhood": "Killarney", "name": "Tammy Peyton", "lat": 53.5872183, "lng": -113.4888864, "id": 69691, "block": "R1A"}, "location_name": "12839 95a St NW", "finish_time": "08:11", "gmaps_url": "https://www.google.ca/maps/place/12839+95a+St+NW,+T5E+3Z8/@53.5872183,-113.4888864,17z", "arrival_time": "08:08", "location_id": "69691"}, {"customNotes": {"status": "Active", "neighborhood": "Killarney", "name": "Candace Cleveland", "lat": 53.58635, "driver notes": "Empties behind gate (theft issues)", "lng": -113.486316, "id": 65001, "block": "R1A"}, "location_name": "9408 128 Ave NW", "finish_time": "08:15", "gmaps_url": "https://www.google.ca/maps/place/9408+128+Ave+NW,+T5E+0H2/@53.58635,-113.486316,17z", "arrival_time": "08:12", "location_id": "65001"}, {"customNotes": {"status": "Active", "neighborhood": "Killarney", "name": "Alexandra Poletz", "lat": 53.587245, "lng": -113.485289, "id": 56230, "block": "R1A"}, "location_name": "12816 93 St NW, T5E 3T2", "finish_time": "08:18", "gmaps_url": "https://www.google.ca/maps/place/12816+93+St+NW,+T5E+3T2/@53.587245,-113.485289,17z", "arrival_time": "08:15", "location_id": "56230"}, {"customNotes": {"status": "Dropoff", "office notes": "***RMV R1B***", "neighborhood": "Killarney", "name": "June Olson", "lat": 53.5883708, "driver notes": "***Dropoff Wed Apr 27 2016***", "lng": -113.4862602, "id": 71843, "block": "R1B, R1A"}, "location_name": "9408 129A Ave NW, T5E -0N7", "finish_time": "08:22", "gmaps_url": "https://www.google.ca/maps/place/9408+129A+Ave+NW,+T5E+-0N7/@53.5883708,-113.4862602,17z", "arrival_time": "08:19", "location_id": "71843"}]';
//   data = JSON.parse(data);