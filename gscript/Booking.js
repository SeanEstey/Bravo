//----------------------------------------------------------------------------
function search(term) {
  /* Search query invoked from Booker client
   * Parses the term arg for conducts appropriate search.
   * term: either Account Number, Postal Code, Address, or Block
   * Returns JSON string: {'search_type': str, 'status': str, 'message': str, 'booking_results': array }
   */
  
  var results = {
    'search_term': term,
    'search_type': ''
  };
  
  if(Parser.isBlock(term))
    results['search_type'] = 'block';
  else if(Parser.isPostalCode(term))
    results['search_type']  = 'postal';
  else if(Parser.isAccountId(term))
    results['search_type']  = 'account';
  
  switch(results['search_type']) {
    case 'block':
      results['booking_results'] = getBookingOptionsByBlock(term);
      results['message'] = 'Booking suggestions for Block <b>' + term + '</b> within next <b>sixteen weeks</b>';
      
      break;
      
    case 'postal':
      results['booking_results'] = getBookingOptionsByPostal(term);
      results['message'] = 'Booking suggestions for Postal Code <b>' + term.substring(0,3) + '</b> within next <b>ten weeks</b>';
      
      break;
      
    case 'account':
      Logger.log('search by account #');
   
      var response = bravoPOST(Config['etap_api_url'], 'get_account', {'account_number':term.slice(1)});
      
      Logger.log('responseCode: ' + JSON.stringify(response.getResponseCode()));
      
      if(response.getResponseCode() == 400) {
        results['status'] = 'failed';
        results['message'] = 'Account <b>' + term + '</b> not found in eTapestry';
        break;
      }
      
      var account = JSON.parse(response.getContentText());
      
      results['account_id'] = account['id'];
      results['account_name'] = account['name'];
      
      var geo = Maps.newGeocoder().geocode(account['address'] + ',' + account['postalCode']);
      
      if(geo.status != 'OK' || geo.results.length != 1) {
        results['status'] = 'failed';
        results['message'] = 'Could not find local address. Make sure to include quadrant (i.e. NW) and Postal Code';
        break;
      }
      
      if(account['nameFormat'] == 3) { // BUSINESS
        results['booking_results'] = getBookingOptionsByPostal(account['postalCode']);
        results['message'] = 'Booking suggestions for account <b>' + account['name'] + '</b> in <b>' + account['postalCode'].substring(0,3) + '</b> within next <b>14 days</b>';
      }
      else {
        results['booking_results'] = getBookingOptionsByRadius(
          geo.results[0].geometry.location.lat, 
          geo.results[0].geometry.location.lng
        );
        results['message'] = 'Booking suggestions for account <b>' + account['name'] + '</b> in <b>10km</b> within next <b>14 days</b>';
      }
 
      break;
      
    // Likely an Address
    default: 
      results['search_type'] = 'address';
    
      var geo = Maps.newGeocoder().geocode(term);
      
      if(geo.status != 'OK' || geo.results.length != 1) {
        results['status'] = 'failed';
        results['message'] = 'Did you search for an address? Could not locate <b>'+term+'</b>. Make sure to include quadrant (i.e. NW) and Postal Code';
        break;
      }

      results['message'] = 'Booking suggestions for <b>' + term + '</b> in <b>10km</b> within next <b>14 days</b>';
      results['booking_results'] = getBookingOptionsByRadius(
        geo.results[0].geometry.location.lat, 
        geo.results[0].geometry.location.lng
      );
 
      break;
  }
  
  return JSON.stringify(results);
}


//----------------------------------------------------------------------------
function makeBooking(account_num, udf, type) {
  /* Makes the booking in eTapestry by posting to Bravo. 
   * This function is invoked from the booker client.
   * type: 'delivery, pickup'
   */
  
  Logger.log('Making ' + type + ' booking for account ' + account_num + ', udf: ' + udf);
  
  var response = bravoPOST(Config['etap_api_url'], 'make_booking', {'account_num':account_num, 'udf':udf, 'type':type});
  
  Logger.log(response.getContentText());
  
  return response.getContentText();
}


//----------------------------------------------------------------------------
function getBookingOptionsByRadius(lat, lng) {
  /* Find booking options within number of days wait and radius defined in
   * Config['booking'].
   * Returns array of Blocks on success, empty array on failure
   */
  
  var today = new Date();
  var two_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * Config['booking']['max_schedule_days_wait']));
  var radius = 4.0;
  
  var found = false;
  
  var bookings = [];
  
  // Start with small radius, continually expand radius until match found
  while(!found) {
    if(radius > Config['booking']['max_block_radius'])
      break;
    
    bookings = Geo.findBlocksWithin(lat, lng, radius, two_weeks);
    
    if(bookings.length > 0)
      found = true;
    else {
      Logger.log('No match found within ' + radius.toString() + ' km. Expanding search.');
      radius += 1.0;
    }
  }
  
  if(found) {
    for(var i=0; i<bookings.length; i++) {
      if(Parser.isRes(bookings[i].block))
        bookings[i]['max_size'] = Config['booking']['size']['residential']['max'];
      else
        bookings[i]['max_size'] = Config['booking']['size']['business']['max'];
    }
  }
 
  // May be empty array
  return bookings;
}

function getBlocksOnDate(date) {
  return Schedule.getCalEventsBetween(Config['res_calendar_id'], date, date);
  
}


//----------------------------------------------------------------------------
function getBookingOptionsByBlock(block) {
  /* Searches schedule for all occurences of block within Config['booking']['search_weeks']
   * On success, returns list of objects: {'block','date','location','event_name','booking_size'},
   * empty list on failure.
   */
  
  var today = new Date();
  var end_date = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * Config['booking']['search_weeks']));
  var res_events = Schedule.getCalEventsBetween(Config['res_calendar_id'], today, end_date);
  var bus_events = Schedule.getCalEventsBetween(Config['bus_calendar_id'], today, end_date);
  var events = res_events.concat(bus_events);
  
  var results = [];
  for(var i=0; i<events.length; i++) { 
    var cal_block = Parser.getBlockFromTitle(events[i].summary);
    
    if(block != cal_block)
      continue;
    
    var result = {
      'block': block, 
      'date': parseDate(events[i].start.date), 
      'location': events[i].location,
      'event_name': events[i].summary.substring(0, events[i].summary.indexOf(']')+1),
      'booking_size':Parser.getBookingSize(events[i].summary)
    };
    
    if(Parser.isRes(block))
      result['max_size'] = Config['booking']['size']['residential']['max'];
    else
      result['max_size'] = Config['booking']['size']['business']['max'];
        
    results.push(result);
  }
  
  results.sort(function(a, b) {
    return a.date.getTime() - b.date.getTime();
  });
  
  return results;  
}
  

//----------------------------------------------------------------------------
function getBookingOptionsByPostal(postal) {
  /* Return Bus and Res calendar events matching postal code, sorted by date. 
   * JSON format 
   */
  
  postal = postal.toUpperCase();
  var today = new Date();
  var ten_weeks = new Date(today.getTime() + (1000 * 3600 * 24 * 7 * 10));
  var res_events = Schedule.getCalEventsBetween(Config['res_calendar_id'], today, ten_weeks);
  var bus_events = Schedule.getCalEventsBetween(Config['bus_calendar_id'], today, ten_weeks);
  var events = res_events.concat(bus_events);
  
  var results = [];
  for(var i=0; i < events.length; i++) {
    var event = events[i];
    
    if(!event.location) {
      Logger.log('Calendar event ' + event.summary + ' missing postal code');
      continue;
    }
    
    var postal_codes = event.location.split(",");
    
    for(var n=0; n<postal_codes.length; n++) {
      if(postal_codes[n].trim() != postal.substring(0,3))
        continue;
      
      var block = Parser.getBlockFromTitle(event.summary);
      var result = {
        'block': block, 
        'date': parseDate(event.start.date), 
        'event_name': event.summary.substring(0, event.summary.indexOf(']')+1),
        'location': event.location,
        'booking_size':Parser.getBookingSize(event.summary)
      };
      
      if(Parser.isRes(block))
        result['max_size'] = Config['booking']['size']['residential']['max'];
      else
        result['max_size'] = Config['booking']['size']['business']['max'];
        
      results.push(result);
    }
  }
  
  results.sort(function(a, b) {
    return a.date.getTime() - b.date.getTime();
  });
  
  return results;  
}