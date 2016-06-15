//---------------------------------------------------------------------
function Signups(map_data, config, _events) {
  /* Constructor that pulls data from entries in Signups worksheet, some
   * schedule data, etc
   * @config: object containing keys: ['etapestry', 'twilio_auth_key', 
   * 'booking', 'cal_ids', 'gdrive']
   * @events: optional list of calendar events
   */
 
  this.map_data = map_data;
  this.etapestry_id = config['etapestry'];
  this.twilio_auth_key = config['twilio_auth_key'];
  this.rules = config['booking'];
  this.cal_ids = config['cal_ids'];
  
  var ss = SpreadsheetApp.openById(config['gdrive']['ss_ids']['bravo']);
  this.sheet = ss.getSheetByName("Signups");

  var data_range = this.sheet.getDataRange();
  var rows = data_range.getValues();
  this.headers = rows.slice(0,1)[0];
  this.signups_values = rows.slice(1);
  this.signups_formulas = data_range.getFormulas().slice(1);

  var tomorrow = new Date(Date.now() + (24 * 3600 * 1000));
  var ten_weeks = new Date(Date.now() + (24 * 3600 * 7 * 10 * 1000));
  
  this.events = _events || Schedule.getEventsBetween(this.cal_ids['res'], tomorrow, ten_weeks);
}

//---------------------------------------------------------------------
Signups.prototype.process = function() {
  /* Go through all Signup entries and assign their
   * Blocks/Neighborhoods/Dropoffs, validate address/phone, and check
   * for duplicates in eTapestry
   */

  for(var index=0; index<this.signups_values.length; index++) {
    var signup = this.signups_values[index];
    var headers = this.headers;
    
    if(signup[headers.indexOf('Dropoff Date')] && signup[headers.indexOf('Natural Block')] && signup[headers.indexOf('Neighborhood')])
      continue;
    
    if(!signup[headers.indexOf('Status')])
      signup[headers.indexOf('Status')] = 'Dropoff';
    
    this.sheet.getRange(index+2, headers.indexOf('Validation')+1).clearNote();
    signup[headers.indexOf('Validation')] = '';
    this.sheet.getRange(index+2, 1, 1, this.sheet.getMaxColumns()).setFontColor('black');
  
    
 //   this.sheet.getRange(index+2+":"+index+2).setFontColor('black');
    
    /*** If no Dropoff date, do full validation ***/
    
    this.assignNaturalBlock(index);
    this.assignBookingBlock(index);
    this.assignTemporaryNotes(index);
    this.checkForDuplicates(index);
    this.validatePhone(index);
    this.validateEmail(index);
    
    // Fix any minor formatting issues
    
    signup[headers.indexOf('Postal Code')] = signup[headers.indexOf('Postal Code')].toUpperCase();
    signup[headers.indexOf('First Name')] = toTitleCase(signup[headers.indexOf('First Name')]);
    signup[headers.indexOf('Last Name')] = toTitleCase(signup[headers.indexOf('Last Name')]);
    signup[headers.indexOf('Email')] = signup[headers.indexOf('Email')].toLowerCase();
    
    // Any missing required fields?
    
    var missing = [];
    
    if(!signup[headers.indexOf('Natural Block')])
      missing.push('Block');
    if(!signup[headers.indexOf('Neighborhood')])
      missing.push('Neighborhood');
    if(!signup[headers.indexOf('Signup Date')])
      missing.push('Signup Date');
    if(!signup[headers.indexOf('Status')])
      missing.push('Status');
    if(!signup[headers.indexOf('Tax Receipt')])
      missing.push('Tax Receipt');
    if(!signup[headers.indexOf('Reason Joined')])
      missing.push('Reason Joined');
    if(!signup[headers.indexOf('First Name')])
      missing.push('First Name');    
    if(!signup[headers.indexOf('Last Name')])
      missing.push('Last Name');    
    if(!signup[headers.indexOf('Address')])
      missing.push('Address'); 
    if(!signup[headers.indexOf('City')])
      missing.push('City'); 
    if(!signup[headers.indexOf('Postal Code')])
      missing.push('Postal');
    
    if(missing.length > 0) {
      var msg = 'Missing fields: ' + missing.join(', ');
      signup[headers.indexOf('Validation')] += msg;
      appendCellNote(this.getRange(index+2, 'Validation'), msg);
      this.getRange(index+2, 'Validation').setFontColor('red');
    }
    
    if(!signup[headers.indexOf('Validation')])
      signup[headers.indexOf('Validation')] = 'OK';
    
    this.sheet.getRange(index+2, 1, 1, this.sheet.getLastColumn()).setValues([signup]);
    
    // Add formula for Projected Route Size and # Occurences
    this.sheet.getRange(
      index+2, this.headers.indexOf('Projected Route Size')+1,
      1, 1
    ).setFormula(this.signups_formulas[index][this.headers.indexOf('Projected Route Size')]);
  }
  
  this.sheet.getDataRange().setHorizontalAlignment('right');
  this.sheet.getDataRange().setFontSize(9);
  this.sheet.getDataRange().setWrap(true);
}


//---------------------------------------------------------------------
Signups.prototype.getPresetBookingBlock = function(index) { 
  /* If Dropoff Date is already predetermined and noted in Office Notes
   * by "DOD May 13" or "Dropoff May 13", parse that date and find the 
   * appropriate Booking Block
   */
  
  var signup = this.signups_values[index];
  var headers = this.headers;
  var dod = /(DOD)|(dropoff)/gi;
  var extra_char = /[^\w\s]/gi;
  
  if(signup[headers.indexOf('Dropoff Date')]) {
    var date = signup[headers.indexOf('Dropoff Date')];
  }
  else { 
    var lines = signup[this.headers.indexOf('Office Notes')].split('\n');
    
    for(var i=0; i<lines.length; i++) {
      if(lines[i].match(dod)) {
        lines[i] = lines[i].replace(dod, '').trim();
        lines[i] = lines[i].replace(extra_char, '');
        
        if(!Date.parse(lines[i])) {
          lines[i] += ', 2016';
          
          if(!Date.parse(lines[i]))
            return false;
        }
        
        lines[i] += " 09:00:00 GMT-0600 (MDT)";
        
        var date = new Date(Date.parse(lines[i]));
      }
    }
  }
  
  if(!date)
    return false;
      
  var address = signup[headers.indexOf("Address")] + ', ' + signup[headers.indexOf("City")] + ", AB";
  var geo = Maps.newGeocoder().geocode(address);
  
  Logger.log('Looking for preset block for entry #' + String(index+1));
  
  var blocks = Geo.findBlocksWithin(
    geo.results[0].geometry.location.lat,
    geo.results[0].geometry.location.lng,
    this.map_data,
    10.0,
    date,
    this.cal_ids['res'],
    this.events
  );
  
  date.setHours(0,0,0,0,0);
  
  var dod_blocks = [];
  
  for(var i=0; i<blocks.length; i++) {
    blocks[i].date.setHours(0,0,0,0,0);
    
    var block_date = new Date(blocks[i].date);
    
    if(block_date.getTime() == date.getTime())
      dod_blocks.push(blocks[i]);
  }
  
  dod_blocks.sort(function(a, b) {
      if(a.distance < b.distance)
        return -1;
      else if(a.distance > b.distance)
        return 1;
      else
        return 0;
  });
  
  Logger.log("Found preset Dropoff Date!");
  Logger.log(dod_blocks[0]);
  
  return dod_blocks[0];
}
    
//---------------------------------------------------------------------
Signups.prototype.assignBookingBlock = function(index) {
  /* Depending on the schedule, dropping off on the Natural Block will 
   * be anywhere between a 1 week wait (good) to 10 weeks (bad).
   * Query Natural Block schedule and try to optimize with a sooner Block.
   
   * Option A: Dropoff Date was known in advance by person who entered
   * the Signup. Parse that Date from Office Notes and find appropriate
   * Block.
   
   * Option B: Look through the schedule for a sooner Block that has
   * capacity and within acceptable km radius.
   
   * Returns Block object (defined in Config) for either Booking Block
   * if optimization successful or Natural Block if not.
   */
  
  var signup = this.signups_values[index];
  var headers = this.headers;
  
  if(!signup[headers.indexOf('Natural Block')])
    return false;
  
  // A. Dropoff Date already preset?
  
  var preset_booking = this.getPresetBookingBlock(index);
  
  if(preset_booking) {
    signup[headers.indexOf('Dropoff Date')] = preset_booking.date;
    signup[headers.indexOf('Booking Block')] = preset_booking.block;
    signup[headers.indexOf('Projected Route Size')] = preset_booking.booking_size;
    var formula = "="+signup[headers.indexOf('Projected Route Size')]+"+ countif(C[-1]:C[-1], R[0]C[-1])"; 
    this.signups_formulas[index][this.headers.indexOf('Projected Route Size')] = formula;
    
    return true;
  }
  
  // B. Look through Schedule for optimized Booking Block  

  var natural_schedule = Schedule.findBlock(
    signup[headers.indexOf('Natural Block')],
    this.events
  );
  
  var geo = Maps.newGeocoder().geocode(
    signup[headers.indexOf('Address')] + ', ' +
    signup[headers.indexOf('City')] + ', AB');
      
  if(geo.status != 'OK') { //|| geo.results.length != 1) {
    signup[headers.indexOf('Validation')] += 'Could not geolocate address to find Booking Block';
    return false;
  }
  
  // Get all posssible bookings within 10km
  var alt_bookings = Booking.getOptionsByRadius(
    geo.results[0].geometry.location.lat, 
    geo.results[0].geometry.location.lng,
    this.map_data,
    this.cal_ids,
    this.rules,
    this.events
  );
  
  var alt_schedule = '';
  var two_days_in_ms = 1000 * 3600 * 24 * 2;
  
  // Disqualify any booking that is maxed out or closer than 2 days away
  for(var i=0; i<alt_bookings.length; i++) {
    if(alt_bookings[i]['booking_size'] > this.rules['size']['res']['max'])
      continue;
    
    var diff = alt_bookings[i]['date'] - new Date();
    
    if(diff < two_days_in_ms)
      continue;
    
    alt_schedule = alt_bookings[i];
    
    var msg = 'Booking Block Distance: ' + alt_schedule['distance'] + '\n';
    appendCellNote(this.getRange(index+2, 'Validation'), msg);
    
    break;
  }
     
  Logger.log('Natural Drop: %s, Alt Drop: %s', 
             JSON.stringify(natural_schedule), JSON.stringify(alt_schedule));
  
  // Need to fill remaining fields: Drop-off Date, Booking Block, Projected Route Size
  
  var use_alt_block = false;
  
  if(!natural_schedule && alt_schedule)
    use_alt_block = true;
  else if(natural_schedule && alt_schedule) {
    if(alt_schedule.date.getTime() < natural_schedule.date.getTime())
      use_alt_block = true;
  }
  
  Logger.log('Booking Block index: %s, Projected Route Size index: %s',
             headers.indexOf('Booking Block'), headers.indexOf('Projected Route Size'));
  
  if(use_alt_block) {
    signup[headers.indexOf('Dropoff Date')] = alt_schedule.date;
    signup[headers.indexOf('Booking Block')] = alt_schedule.block;
    signup[headers.indexOf('Projected Route Size')] = alt_schedule.booking_size;
  }
  else {
    signup[headers.indexOf('Dropoff Date')] = natural_schedule.date;
    signup[headers.indexOf('Booking Block')] = natural_schedule.block;
    signup[headers.indexOf('Projected Route Size')] = natural_schedule.booking_size;
  }
  
  // Query scheduled Block Size if not on Calendar
  
  if(signup[headers.indexOf('Projected Route Size')] == '?') {
    var data = {
      'query_category': this.etapestry_id['query_category'],
      'query':signup[headers.indexOf('Booking Block')], 
      'date':date_to_ddmmyyyy(signup[headers.indexOf('Dropoff Date')])
    };
    
    var response = Server.call('get_scheduled_route_size', data, this.etapestry_id);
    
    if(response.getResponseCode() == 200) {
      var booked = response.getContentText().substring(0, response.getContentText().indexOf('/'));
      signup[headers.indexOf('Projected Route Size')] = booked;
    }
  }
  
  // Set Formula to re-calculate Booking Size with all pending signups matching Booking Block
  
  var formula = "="+signup[headers.indexOf('Projected Route Size')]+"+ countif(C[-1]:C[-1], R[0]C[-1])";
  
  this.signups_formulas[index][this.headers.indexOf('Projected Route Size')] = formula;
  
  Logger.log('Booking block found: ' + signup[headers.indexOf('Booking Block')]);
  
  return true;
}

//---------------------------------------------------------------------
Signups.prototype.assignTemporaryNotes = function(index) {
  var signup = this.signups_values[index];
  var headers = this.headers;
  
  if(!signup[headers.indexOf('Dropoff Date')])
    return false;
  
  signup[headers.indexOf('Driver Notes')] = 
    '***Dropoff ' + signup[headers.indexOf('Dropoff Date')].toDateString() + '***';
  
  if(signup[headers.indexOf('Booking Block')] != signup[headers.indexOf('Natural Block')]) {
    signup[headers.indexOf('Office Notes')] = signup[headers.indexOf('Office Notes')].replace(/\*{3}RMV\s(B|R)\d{1,2}[a-zA-Z]{1}\*{3}(\n|\r)?/g, '');
    signup[headers.indexOf('Office Notes')] += '\n***RMV ' + signup[headers.indexOf('Booking Block')] + '***';
  }
}

//---------------------------------------------------------------------
Signups.prototype.assignNaturalBlock = function(index) {
  /* Use Google Maps Geolocator and KML rows to set Residential Block and Neighborhood defined 
   * fields. 
   * Returns: map title string on success, false if partial or no match found.
   * Map title format:
   * '1E [Neighborhood1, Neighborhood2, Neighborhood3]' for Edmonton
   * '3G GREATER_AREA_CITY [Neighborhood1, Neighborhood2, Neighborhood3]' for surrounding area
   */
  
  /* TODO: Split this into 2 functions. 1) Validate address, postal, assign neighborhood, 2) Assign Block */
  
  var signup = this.signups_values[index];
  var headers = this.headers;
  var err = 'Failed to find Natural Block. Reason: ';
  
  // A. Geolocate Address
  
  if(!signup[headers.indexOf('Address')])
    return false;
  
  var replace_address = true;

  var result = Geo.geocodeBeta(signup[headers.indexOf('Address')], 
                            signup[headers.indexOf('City')], 
                            signup[headers.indexOf('Postal Code')]);
  
  if(!Geo.hasAddressComponent(result, 'postal_code') || 
     !Geo.hasAddressComponent(result, 'route') || 
     !Geo.hasAddressComponent(result, 'street_number') ||
     !("location" in result.geometry)) {
       
       replace_address = false;
       
       Logger.log(signup[headers.indexOf('Validation')] += 'Couldnt validate address. Using approximation.\n\n');
       
       appendCellNote(this.getRange(index+2, 'Validation'), 
                      'Using address approximation "' + result.formatted_address + '"\n');
       
       this.getRange(index+2, 'Validation').setFontColor('red');
       this.getRange(index+2, 'Address').setFontColor('red');
    }
  
  for(var j=0; j<result.address_components.length; j++) {
    if(result.address_components[j]['types'].indexOf('postal_code') == -1)
      continue;
    
    var postal = result.address_components[j]['short_name'];
    
    if(postal.substring(0,3) != signup[headers.indexOf('Postal Code')].substring(0,3)) {
      var msg = "Replacing postal code \"" + signup[headers.indexOf('Postal Code')] + "\"\n";
      appendCellNote(this.getRange(index+2, 'Validation'), msg);
      signup[headers.indexOf('Postal Code')] = postal;
    }
  }
 
  // B. Search KML map data to identify Natural Block
  
  var map_title = Geo.findMapTitle(
    result.geometry.location.lat, 
    result.geometry.location.lng, 
    this.map_data);
  
  if(!map_title) {
    Logger.log(signup[this.headers.indexOf('Validation')] += err + "Failed to find KML map");
    return false;
  }
  
  signup[this.headers.indexOf('Natural Block')] = Parser.getBlockFromTitle(map_title);  
  
  // C. Get Block Size
  
  var response = Server.call('get_block_size', {
      'query_category':this.etapestry_id['query_category'],
      'query': signup[this.headers.indexOf('Natural Block')]
    },
    this.etapestry_id
  );
  
  if(response.getResponseCode() == 200)
    signup[headers.indexOf('Natural Block Size')] = response.getContentText();
  else
    signup[headers.indexOf('Natural Block Size')] = '?';
  
  // D. Find Neighborhood (or neighborhood groupings)
  
  var map_neighborhoods = map_title.substring(
      map_title.indexOf("[")+1, 
      map_title.indexOf("]")).split(',');
  
  // If either no Neighborhood name geolocated, or Neighborhood is not found
  // in the list in the map title, then assign the entire group of neighborhoods
  
  for(var i=0; i<result.address_components.length; i++) {
    if(result.address_components[i].types.indexOf('neighborhood') > -1) {
      signup[this.headers.indexOf('Neighborhood')] = result.address_components[i]['short_name'];
    }
  }

  if(!signup[this.headers.indexOf('Neighborhood')])
    signup[this.headers.indexOf('Neighborhood')] = map_neighborhoods.join(',');
  
  if(map_neighborhoods.indexOf(signup[this.headers.indexOf('Neighborhood')]) == -1) {
    var msg = "Neighborhood \"" + signup[this.headers.indexOf('Neighborhood')] + "\" may be invalid. Using group from Block definition.\n"; 
    appendCellNote(this.getRange(index+2, 'Validation'), msg);
    Logger.log(msg);
    
    signup[this.headers.indexOf('Neighborhood')] = map_neighborhoods.join(',');
  }
  
  if(replace_address) {
    if(signup[this.headers.indexOf('Address')] != result.formatted_address.substring(0, result.formatted_address.indexOf(','))) {
      var msg = "Corrected address spelling: \"" + signup[this.headers.indexOf('Address')] + "\"\n"; 
      appendCellNote(this.getRange(index+2, 'Validation'), msg);   
      signup[this.headers.indexOf('Address')] = result.formatted_address.substring(0, result.formatted_address.indexOf(','));
    }
  }
 
  return map_title;
}

//---------------------------------------------------------------------
Signups.prototype.getRange = function(row, header) {
  return this.sheet.getRange(row, this.headers.indexOf(header)+1);
}

//---------------------------------------------------------------------
Signups.prototype.checkForDuplicates = function(index) {
  /* Check the most recently added form signup for duplicates in eTapestry */
  
  var signup = this.signups_values[index];
  var headers = this.headers;

  var criteria = {
    'address': signup[headers.indexOf('Address')],
    'name': signup[headers.indexOf('First Name')] + ' ' + signup[headers.indexOf('Last Name')],
  };
   
  if(signup[headers.indexOf('Email')])
    criteria['email'] = signup[headers.indexOf('Email')];
  
  var response = Server.call('check_duplicates', criteria, this.etapestry_id);
  
  if(response.getResponseCode() == 200 && response.getContentText())
    signup[headers.indexOf('Existing Account')] = response.getContentText();
}

//---------------------------------------------------------------------
Signups.prototype.validateEmail = function(index) {
  var signup_values = this.signups_values[index];
  
  if(!signup_values[this.headers.indexOf('Email')].match(/[\w-]+@([\w-]+\.)+[\w-]+/gi)) {
    var msg = "Deleted invalid email '" + signup_values[this.headers.indexOf('Email')] + "'\n";
    appendCellNote(this.getRange(index+2, 'Validation'), msg);
  
    signup_values[this.headers.indexOf('Email')] = '';
    
    return false;
  }
  
  return true;
}

//---------------------------------------------------------------------
Signups.prototype.validatePhone = function(index) {
  var signup = this.signups_values[index];
  
  var url = 'https://lookups.twilio.com/v1/PhoneNumbers/';
  var phone = String(signup[this.headers.indexOf('Primary Phone')]);
  
  // Make format: ###-###-####
  phone = phone.replace(/\D/g,'');
  if(phone.length == 10) {
    phone = phone.substring(0,3) + '-' + phone.substring(3,6) + '-' + phone.substring(6,10);
    signup[this.headers.indexOf('Primary Phone')] = phone;
  }
  
  if(!this.twilio_auth_key)
    return false;
  
  var headers = {
    "Authorization" : "Basic " + Utilities.base64Encode(this.twilio_auth_key)
  };
    
  try {
    var response = UrlFetchApp.fetch(url+phone+'?Type=carrier', {'method':'GET',  'muteHttpExceptions': true, 'headers':headers});
  }
  catch(e) {
    Logger.log(e);
    return false;
  }
  
  var responseJSON = JSON.parse(response);
  
  // Success
  if(responseJSON.hasOwnProperty('carrier')) {
    var carrier = responseJSON['carrier']['name'].split(' ')[0];
    
    appendCellNote(this.getRange(index+2, 'Validation'), 'Phone type: ' + toTitleCase(responseJSON['carrier']['type']) + ' (' + carrier + ')\n');
    
    if(responseJSON['carrier']['type'] == 'mobile')
      signup[this.headers.indexOf('Mobile Phone')] = phone;
  }
  // Fail
  else {
    if(responseJSON['status'] == 404) {
      var msg = 'Invalid phone number: ' + phone + '\n';
      appendCellNote(this.getRange(index+2, 'Validation'), msg);
      this.getRange(index+2, 'Validation').setFontColor('red');
      this.getRange(index+2, 'Primary Phone').setFontColor('red');
      signup[this.headers.indexOf('Validation')] += msg;
    }

    Logger.log(responseJSON);
    
    return false;
  }
  
  return true;
}

//---------------------------------------------------------------------
Signups.prototype.buildPayload = function(ui) {
  /* Send 'em to eTapestry via Bravo */
  
  var request_id = new Date().getTime();
  var payload = [];
  
  // Select signups which have been audited but not yet uploaded,
  // have all required fields
  for(var i=0; i<this.signups_values.length; i++) {
    var signup = this.signups_values[i];

    if(!signup[this.headers.indexOf('Audited')])
      continue;
    if(signup[this.headers.indexOf('Upload Status')])
      continue;
    if(!signup[this.headers.indexOf('Dropoff Date')])
      continue;
    if(!signup[this.headers.indexOf('Natural Block')])
      continue;
    if(!signup[this.headers.indexOf('Booking Block')])
      continue;
    if(!signup[this.headers.indexOf('Neighborhood')])
      continue;
    
    var block = signup[this.headers.indexOf('Natural Block')] + ',' + signup[this.headers.indexOf('Booking Block')];
    
    if(signup[this.headers.indexOf('Natural Block')] == signup[this.headers.indexOf('Booking Block')])
      block = signup[this.headers.indexOf('Natural Block')];
    
    var udf = {
      'Status': signup[this.headers.indexOf('Status')],
      'Signup Date': date_to_ddmmyyyy(signup[this.headers.indexOf('Signup Date')]),
      'Dropoff Date': date_to_ddmmyyyy(signup[this.headers.indexOf('Dropoff Date')]),
      'Next Pickup Date': date_to_ddmmyyyy(signup[this.headers.indexOf('Dropoff Date')]),
      'Neighborhood': signup[this.headers.indexOf('Neighborhood')],
      'Block': block,
      'Driver Notes': signup[this.headers.indexOf('Driver Notes')],
      'Office Notes': signup[this.headers.indexOf('Office Notes')],
      'Tax Receipt': signup[this.headers.indexOf('Tax Receipt')],
      'Reason Joined': signup[this.headers.indexOf('Reason Joined')],
      'Referrer': signup[this.headers.indexOf('Referrer')],
     };
    
    var persona = {
      'personaType': signup[this.headers.indexOf('Persona Type')],
      'address': signup[this.headers.indexOf('Address')],
      'city': signup[this.headers.indexOf('City')],
      'state': 'AB',
      'country': 'CA',
      'postalCode': signup[this.headers.indexOf('Postal Code')],
      'email': signup[this.headers.indexOf('Email')],
      'phones': [
      {'type': 'Voice', 'number': signup[this.headers.indexOf('Primary Phone')]},
        {'type': 'Mobile', 'number': signup[this.headers.indexOf('Mobile Phone')]}
      ]
    };
    
    if(signup[this.headers.indexOf('Name Format')] == 'Individual') {
      persona['nameFormat'] = 1;
      persona['name'] = signup[this.headers.indexOf('First Name')] + ' ' + 
        signup[this.headers.indexOf('Last Name')];
      persona['sortName'] = signup[this.headers.indexOf('Last Name')] + ', ' + 
        signup[this.headers.indexOf('First Name')];
      persona['firstName'] = signup[this.headers.indexOf('First Name')];
      persona['lastName'] = signup[this.headers.indexOf('Last Name')];
      persona['shortSalutation'] = signup[this.headers.indexOf('First Name')];
      persona['longSalutation'] = signup[this.headers.indexOf('Title')] + ' ' + 
        signup[this.headers.indexOf('Last Name')];
      persona['envelopeSalutation'] = signup[this.headers.indexOf('Title')] + ' ' + 
        signup[this.headers.indexOf('First Name')] + ' ' + signup[this.headers.indexOf('Last Name')];
    }
    else {
      persona['nameFormat'] = 3;
      persona['name'] = signup[this.headers.indexOf('Business Name')];
      persona['sortName'] = persona['name'];
      udf['Contact'] = signup[this.headers.indexOf('Contact Person')];
    }    
    
    payload.push({
      'row': i+2,
      'request_id': request_id,
      'existing_account': signup[this.headers.indexOf('Existing Account')],
      'persona': persona,
      'udf': udf
    });
  }
  
  if(ui != undefined) {
    if(ui.alert(
      'Please confirm',
      payload.length + ' accounts audited and prepared for upload. Go ahead?',
      ui.ButtonSet.YES_NO) == ui.Button.NO)
      return false;
  }
    
  return payload;
}

//---------------------------------------------------------------------
Signups.prototype.emailUploaded = function() {
  /* Email welcome letters w/ Dropoff Date to uploaded Signups */
  
  var num_welcomes_sent = 0;
  
  // Email all Uploaded signups who have registered email addresses  
  
  for(var i=0; i<this.signups_values.length; i++) {
    var signup = this.signups_values[i];
    
    if(!isNumber(signup[this.headers.indexOf('Upload Status')]) && 
       signup[this.headers.indexOf('Upload Status')] != 'Success')
      continue;
    
    if(!signup[this.headers.indexOf('Email')])
      continue;
    
    if(signup[this.headers.indexOf('Email Status')])
      continue;
    
    var options = {
      'muteHttpExceptions': true,
      'method' : 'post',
      'contentType': 'application/json',
      "payload" : JSON.stringify({
        "subject": "Welcome to Empties to Winn",
        "template": "email/welcome.html",
        "recipient": signup[this.headers.indexOf('Email')],
        "data": { 
          "first_name": signup[this.headers.indexOf('First Name')],
          "address": signup[this.headers.indexOf('Address')],
          "postal": signup[this.headers.indexOf('Postal Code')],
          "dropoff_date": signup[this.headers.indexOf('Dropoff Date')].toDateString(),
          "account": {
            "email": signup[this.headers.indexOf('Email')]
          },
          "from": {
            "worksheet": "Signups",
            "row": i+2,
            "upload_status": signup[this.headers.indexOf('Upload Status')],
          }
        }
      })
    };
  
    var response = UrlFetchApp.fetch(Settings['bravo_url'] + '/email/send', options);
    
    Logger.log(response.getContentText());
     
    num_welcomes_sent++;
  }
  
  log(num_welcomes_sent + ' welcome emails sent.', true);
}