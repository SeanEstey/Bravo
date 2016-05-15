function Schedule() {}

/* Block JSON object: {
  'block': string,
  'date': Date obj,
  'booking_size': number,
  'block_size': number,
  'location': string
*/

//----------------------------------------------------------------------------
// Returns all events from ETW Residential calendar between provided Dates
Schedule.getCalEventsBetween = function(calendar_id, start_date, end_date) {
  if(start_date == end_date)
    end_date = new Date(start_date.getTime() + (1000 * 3600 * 1));
    
  try {
    var events = Calendar.Events.list(
      calendar_id, {
        timeMin: start_date.toISOString(),
        timeMax: end_date.toISOString(),
        singleEvents: true,
        orderBy: 'startTime'
    });
  }
  catch(e) {
    var msg = 
      'Msg: ' + e.message + '\\n' +
      'File: ' + e.fileName + '\\n' + 
      'Line: ' + e.lineNumber;    
    log(msg, true);
  }
  
  return events.items;
}

//----------------------------------------------------------------------------
// Search events argument for first occuring block
// Return JSON {'block': String, 'date': Date Object, 'block_size': Number, 'booking_size': Number, 'event_name': String }
Schedule.getNextBlock = function(events, block) {
  for(var i=0; i < events.length; i++) {
    var event = events[i];
    
    var calendar_block = Parser.getBlockFromTitle(event.summary);
    
    if(calendar_block == block) {
      return { 
        'block': block,
        'date': parseDate(event.start.date),
        'booking_size': Parser.getBookingSize(event.summary),
        'block_size': Parser.getBlockSize(event.summary),
        'event_name': event.summary.substring(0, events[i].summary.indexOf(']')+1),
        'location': event.location
      }
    }
  }
  
 // log('No schedule found for block ' + block, true);
  
  return false;
}

// Search events argument for next scheduled run in postal code
// Return JSON {'block': String, 'date': Date Object, 'block_size': Number, 'booking_size': Number }
//----------------------------------------------------------------------------
Schedule.getNextRunWithin = function(events, postal, max_size) {
  postal = postal.toUpperCase();
  
  var today = new Date();
  
  for(var i=0; i < events.length; i++) {
    var event = events[i];
    
    if(!event.location) {
      log('Calendar event ' + event.summary + ' missing postal code', true);
      continue;
    }
    
    var postal_codes = event.location.split(",");
    
    for(var n=0; n<postal_codes.length; n++) {
      if(postal_codes[n].trim() != postal.substring(0,3))
        continue;
      
      var event_date = parseDate(event.start.date);
      var ms_time_diff = event_date.getTime() - today.getTime();
      var ms_in_day = 1000 * 3600 * 24; 
      
      var block_size = Parser.getBlockSize(event.summary);
      var booking_size = Parser.getBookingSize(event.summary);
      
      if(block_size <= max_size) {
        var block = Parser.getBlockFromTitle(event.summary);
        return {
          'block': block, 
          'date': event_date, 
          'block_size':block_size, 
          'booking_size':booking_size,
          'location': event.location
        };
      }
    }
  }
  
  return false;
}

//---------------------------------------------------------------------
Schedule.updateCalendarRunSizes = function(cal_id, start_date, num_events, overwrite_block_sizes) { 
  var events = Calendar.Events.list(cal_id, {
    timeMin: start_date.toISOString(),
    singleEvents: true,
    orderBy: 'startTime',
    maxResults: num_events
  });
  
  for(var i=0; i<num_events; i++) {
    var event = events.items[i];
    var block = Parser.getBlockFromTitle(event.summary);
    
    if(!block)
      continue;
    
    Logger.log('Updating event #' + String(i+1) + ' ' + event.summary);
    
    var end_index = event.summary.indexOf("(")-2;
    
    // Left uncommented, Will not update block count values
    if(!overwrite_block_sizes && end_index >= 0)
      continue;
    
    if(end_index < 0)
      end_index = event.summary.length-1;
        
    event.summary = event.summary.substring(0,end_index+1);
    var date = date_to_ddmmyyyy(parseDate(event.start.date));
 
    var data = {
      'query_category': Config['etap_query_category'],
      'query':block, 
      'date':date
    };
    
    var response = bravoPOST(Config['etap_api_url'], 'get_scheduled_block_size', data);
    
    if(response.getResponseCode() != 200) {
      if(response.getResponseCode() == 400) {
        log('No eTap query match for ' + event.summary, true);
        continue;
      }
      else if(response.getResponseCode() == 502) {
        log('Server timeout for ' + event.summary, true);
        continue;
      }
      else {
        log('Error ' + String(response.getResponseCode()) + '\n.' + response.getContentText(), true);
        continue;
      }
    }
    
    // TODO: Look through Signups and add the count for any Booking Blocks matching 'block'
        
    var new_event = {
      summary: event.summary + " (" + String(response.getContentText()) + ")",
      location: event.location,
      start: {
        date: event.start.date
      },
      end: {
        date: event.end.date
      }
    };
      
    var booking_size = ''
    
    if(Parser.isRes(block))
      booking_size = Config['booking']['size']['residential'];
    else
      booking_size = Config['booking']['size']['business'];
   
    // Format: "scheduled_size/block_size"
    size = Number(response.getContentText().substring(0,response.getContentText().indexOf('/')));
  
    if(size < booking_size['medium'])
      new_event['colorId'] = Config['calendar_color_id']['green'];
    else if(size >= booking_size['medium'] && size < booking_size['large'])
      new_event['coloured'] = Config['calendar_color_id']['yellow'];
    else if(size >= booking_size['large'] && size < booking_size['max'])
      new_event['colorId'] = Config['calendar_color_id']['orange'];
    else if(size >= booking_size['max'])
      new_event['colorId'] = Config['calendar_color_id']['light_red'];

    Logger.log(block + ' size: ' + response.getContentText());
        
    Calendar.Events.insert(new_event, cal_id);
    Calendar.Events.remove(cal_id, event.id);
  }
}

//---------------------------------------------------------------------
// Pull eTapestry data from all Residential/Business runs scheduled for
// specified date and submit them to Viamente
Schedule.buildRoutes = function(calendar_id, date) {
  var routed_folder = DriveApp.getFolderById(Config['gdrive_routed_folder_id']);
  var route_template = DriveApp.getFileById('1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c');
  
  var later = new Date(date.getTime() + (1000 * 3600 * 1));
  
  var res_events = Calendar.Events.list(calendar_id, {
    timeMin: date.toISOString(),
    timeMax: later.toISOString(),
    singleEvents: true,
    orderBy: 'startTime',
  });
  
  for(var i=0; i < res_events.items.length; i++) {
    var event = res_events.items[i];
    var date = date_to_ddmmyyyy(parseDate(event.start.date));  
    var block = Parser.getBlockFromTitle(event.summary);
      
    // Build Template file in routed folder
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var today = new Date();
    var route_title = months[today.getMonth()] + ' ' + today.getDate() + ': ' + block;
    
    route_template.makeCopy(route_title, routed_folder);
  }
}