function Schedule() {}

/* Block JSON object: {
  'block': string,
  'date': Date obj,
  'booking_size': number,
  'block_size': number,
  'location': string
*/

//----------------------------------------------------------------------------
Schedule.getEventsBetween = function(calendar_id, start_date, end_date) {  
  /* Returns all events from ETW Residential calendar between provided Dates */
  
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
    Logger.log(msg);

    return false;
  }
  
  return events.items;
}

//----------------------------------------------------------------------------
Schedule.findBlock = function(block_name, events) {
  /* Search events argument for first occuring block
   * Return JSON {'block': String, 'date': Date Object, 'block_size': Number, 
   * 'booking_size': Number, 'event_name': String }
   */
  
  for(var i=0; i < events.length; i++) {
    var event = events[i];
    
    var calendar_block = Parser.getBlockFromTitle(event.summary);
    
    if(calendar_block == block_name) {
      return { 
        'block': block_name,
        'date': parseDate(event.start.date),
        'booking_size': Parser.getBookingSize(event.summary),
        'block_size': Parser.getBlockSize(event.summary),
        'event_name': event.summary.substring(0, events[i].summary.indexOf(']')+1),
        'location': event.location
      }
    }
  }
    
  return false;
}


//---------------------------------------------------------------------
Schedule.updateCalendarRunSizes = function(cal_id, start_date, num_events, 
                                           booking_rules, etap_config) { 
  /* Update calendar events for each Block with num accounts booked 
   * and total Block size 
   */
  
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
    if(end_index >= 0)
      continue;
    
    if(end_index < 0)
      end_index = event.summary.length-1;
        
    event.summary = event.summary.substring(0,end_index+1);
    var date = date_to_ddmmyyyy(parseDate(event.start.date));
 
    var data = {
      'query_category': etap_config['query_category'],
      'query':block, 
      'date':date
    };
    
    var response = Server.call('get_scheduled_block_size', data, etap_config);
    
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
      booking_size = booking_rules['size']['res'];
    else
      booking_size = booking_rules['size']['bus'];
   
    // Format: "scheduled_size/block_size"
    size = Number(response.getContentText().substring(0,response.getContentText().indexOf('/')));
  
    if(size < booking_size['medium'])
      new_event['colorId'] = Settings['calendar_color_id']['green'];
    else if(size >= booking_size['medium'] && size < booking_size['large'])
      new_event['coloured'] = Settings['calendar_color_id']['yellow'];
    else if(size >= booking_size['large'] && size < booking_size['max'])
      new_event['colorId'] = Settings['calendar_color_id']['orange'];
    else if(size >= booking_size['max'])
      new_event['colorId'] = Settings['calendar_color_id']['light_red'];

    Logger.log(block + ' size: ' + response.getContentText());
        
    Calendar.Events.insert(new_event, cal_id);
    Calendar.Events.remove(cal_id, event.id);
  }
}