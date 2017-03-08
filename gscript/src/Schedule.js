function Schedule(){}
/* Block JSON object: {
  'block': string,
  'date': Date obj,
  'booking_size': number,
  'block_size': number,
  'location': string
*/

//----------------------------------------------------------------------------
Schedule.getEventsBetween = function(cal_id, start_date, end_date) {  
  /* Returns all events from ETW Residential calendar between provided Dates */
  
  if(start_date == end_date)
    end_date = new Date(start_date.getTime() + (1000 * 3600 * 1));
    
  try {
    var events = Calendar.Events.list(
      cal_id, { 
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
