//---------------------------------------------------------------------
function Signups(conf) {
  /* Load agcy conf + Signups wksheet data + event schedule + maps data
   */
 
  this.conf = conf;
  this.wks = SpreadsheetApp.openById(conf['BRAVO_SS_ID']).getSheetByName("Signups");
  this.wks_hdr = this.wks.getRange(1,1,1,this.wks.getMaxColumns()).getValues()[0];
  var data_rng = this.wks.getDataRange();
  this.wks_values = data_rng.getValues().slice(1);
  this.wks_fmlas = data_rng.getFormulas().slice(1);
  this.maps = API('/maps/get', conf, null);
  this.events = Schedule.getEventsBetween(
    conf['CAL_IDS']['RES'],
    new Date(Date.now() + DAY_MS),
    new Date(Date.now() + WEEK_MS * 12));
}

//---------------------------------------------------------------------
Signups.prototype.process = function() {
  /* Assign Block/Drop Block/Area/Drop Date, 
   * validate address/phone, check for eTap duplicates
   */

  var hdr = this.wks_hdr;
  
  for(var index=0; index<this.wks_values.length; index++) {
    var signup = this.wks_values[index];
    
    if(signup[hdr.indexOf('Drop Date')] && signup[hdr.indexOf('Block')] && signup[hdr.indexOf('Area')])
      continue;
    
    Logger.log('processing row %s', (index+1));
    
    if(!signup[hdr.indexOf('Status')])
      signup[hdr.indexOf('Status')] = 'Dropoff';
    
    this.wks.getRange(index+2, hdr.indexOf('Valid')+1).clearNote();
    signup[hdr.indexOf('Valid')] = '';
    this.wks.getRange(index+2, 1, 1, this.wks.getMaxColumns()).setFontColor('black');
  
    /*** If no Drop Date, do full validation ***/
    
    this.assignBlock(index);
    this.assignDrop(index);
    //this.assignTemporaryNotes(index);
    this.checkForDuplicates(index);
    this.validatePhone(index);
    this.validateEmail(index);
    
    // Fix any minor formatting issues
    
    signup[hdr.indexOf('Postal')] = signup[hdr.indexOf('Postal')].toUpperCase();
    signup[hdr.indexOf('First')] = toTitleCase(signup[hdr.indexOf('First')]);
    signup[hdr.indexOf('Last')] = toTitleCase(signup[hdr.indexOf('Last')]);
    signup[hdr.indexOf('Email')] = signup[hdr.indexOf('Email')].toLowerCase();
    
    // Any missing required fields?
    
    var missing = [];
    
    if(!signup[hdr.indexOf('Block')])
      missing.push('Block');
    if(!signup[hdr.indexOf('Drop Block')])
      missing.push('Drop Block');
    if(!signup[hdr.indexOf('Area')])
      missing.push('Area');
    if(!signup[hdr.indexOf('Date')])
      missing.push('Date');
    if(!signup[hdr.indexOf('Status')])
      missing.push('Status');
    if(!signup[hdr.indexOf('Receipt')])
      missing.push('Receipt');
    if(!signup[hdr.indexOf('Reason')])
      missing.push('Reason');
    if(!signup[hdr.indexOf('First')])
      missing.push('First');    
    if(!signup[hdr.indexOf('Last')])
      missing.push('Last');    
    if(!signup[hdr.indexOf('Address')])
      missing.push('Address'); 
    if(!signup[hdr.indexOf('City')])
      missing.push('City'); 
    if(!signup[hdr.indexOf('Postal')])
      missing.push('Postal');
    
    if(missing.length > 0) {
      var msg = 'Missing fields: ' + missing.join(', ');
      Logger.log(msg);
      this.setValid(index, false); 
      appendCellNote(this.getCellRange(index+2, 'Valid'), msg);
    }
    
    if(!signup[hdr.indexOf('Valid')]) {
      Logger.log("Valid!");
      this.setValid(index, true);
    }
    
    this.wks.getRange(index+2, 1, 1, this.wks.getLastColumn()).setValues([signup]);
       
    this.getCellRange(index+2, "Route Size")
      .setFormula(this.wks_fmlas[index][hdr.indexOf("Route Size")]);
    
    var drop_fmla = '="Dropoff " & R[0]C[-1] & TEXT(R[0]C[-3]," mmm dd")';
    
    this.getCellRange(index+2, "Drop Notes")
      .setFormula(drop_fmla)
  }
  
  var rng = this.wks.getRange(2, 3, this.wks.getMaxRows()-2, this.wks.getMaxColumns()-3);
  rng.setHorizontalAlignment('left');
  rng.setFontSize(10);
}

//---------------------------------------------------------------------
Signups.prototype.getPresetBookingBlock = function(index) { 
  /* If Drop Date is already predetermined and noted in Office Notes
   * by "DOD May 13" or "Dropoff May 13", parse that date and find the 
   * appropriate Drop Block.
   * 
   * Returns Block object on success, false on failure.
   * 
   * Throws Exception if maps error or Drop Date provided but no Block found.
   */
  
  var signup = this.wks_values[index];
  var hdr = this.wks_hdr;
  var dod = /(DOD)|(dropoff)/gi;
  var extra_char = /[^\w\s]/gi;
  
  if(signup[hdr.indexOf('Drop Date')]) {
    var date = signup[hdr.indexOf('Drop Date')];
  }
  else { 
    var lines = signup[this.wks_hdr.indexOf('Office Notes')].split('\n');
    
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
      
  var address = signup[hdr.indexOf("Address")] + ', ' + signup[hdr.indexOf("City")] + ", AB";
  var geo = Maps.newGeocoder().geocode(address);
  
  Logger.log('Looking for preset block for entry #' + String(index+1));
  
  // Get all Blocks up until Drop Date, then we'll remove any earlier ones
  var blocks = Geo.findBlocksWithin(
    geo.results[0].geometry.location.lat,
    geo.results[0].geometry.location.lng,
    this.maps,
    10.0,
    date,
    this.conf['CAL_IDS']['RES'],
    this.events
  );
    
  // If no Blocks found, throw error
  if(blocks instanceof Error) 
    throw new Error("Error in maps");
  
  date.setHours(0,0,0,0,0);
  
  var dod_blocks = [];
  
  for(var i=0; i<blocks.length; i++) {
    blocks[i].date.setHours(0,0,0,0,0);
    
    var block_date = new Date(blocks[i].date);
    
    if(block_date.getTime() == date.getTime())
      dod_blocks.push(blocks[i]);
  }
  
  if(dod_blocks.length == 0)
    throw new Error("Could not find Block on given Drop Date!");
    
  dod_blocks.sort(function(a, b) {
      if(a.distance < b.distance)
        return -1;
      else if(a.distance > b.distance)
        return 1;
      else
        return 0;
  });
  
  Logger.log("Found preset Drop Date!");
  Logger.log(dod_blocks[0]);
  
  return dod_blocks[0];
}
    
//---------------------------------------------------------------------
Signups.prototype.assignDrop = function(index) {
  /* Depending on the schedule, dropping off on the Block will 
   * be anywhere between a 1 week wait (good) to 10 weeks (bad).
   * Query Block schedule and try to optimize with a sooner Block.
   
   * Option A: Drop Date was known in advance by person who entered
   * the Signup. Parse that Date from Office Notes and find appropriate
   * Block.
   
   * Option B: Look through the schedule for a sooner Block that has
   * capacity and within acceptable km radius.
   
   * Returns Block object (defined in Config) for either Drop Block
   * if optimization successful or Block if not.
   */
  
  var signup = this.wks_values[index];
  var hdr = this.wks_hdr;
  
  if(!signup[hdr.indexOf('Block')])
    return false;
  
  // A. Drop Date already preset?
    
  try {
    var preset_booking = this.getPresetBookingBlock(index);
  }
  catch(e) {
    appendCellNote(this.getCellRange(index+2, 'Valid'), e.name + ': ' + e.message);
    return false;
  }
  
  if(preset_booking) {
    signup[hdr.indexOf('Drop Date')] = preset_booking.date;
    signup[hdr.indexOf('Drop Block')] = preset_booking.block;
    signup[hdr.indexOf('Route Size')] = preset_booking.booking_size;
    var formula = "="+signup[hdr.indexOf('Route Size')]+"+ countif(C[-1]:C[-1], R[0]C[-1])"; 
    this.wks_fmlas[index][hdr.indexOf('Route Size')] = formula;
    return true;
  }
  
  // B. Look through Schedule for optimized Drop Block  

  var natural_schedule = Schedule.findBlock(
    signup[hdr.indexOf('Block')],
    this.events
  );
  
  var alt_bookings = API(
    '/booker/search',
    this.conf, {
      "query": (signup[hdr.indexOf('Address')]+', '+signup[hdr.indexOf('City')]+', AB').trim(),
      "radius": "6.0",
      "weeks": "10"});
  
  if(alt_bookings['status'] != "success") {
    Logger.log(alt_bookings['description']);
    return false;
  }
  
  alt_bookings = alt_bookings['results'];
  var alt_schedule = '';
  
  // Disqualify any booking that is maxed out or closer than 2 days away
  for(var i=0; i<alt_bookings.length; i++) {
    if(alt_bookings[i]['booked'] > this.conf['MAX_RES_BOOK_SZ'])
      continue;
    
    var j = alt_bookings[i]['event']['start']['date'].split('-');
    var local_dt = new Date(new Date(j[1] + '/' + j[2] + '/' + j[0]).getTime() + 7*60*60*1000);
    alt_bookings[i]['date'] = local_dt;
    var diff = alt_bookings[i]['date'] - new Date();
    if(diff < DAY_MS * 2)
      continue;
    alt_schedule = alt_bookings[i];
    var msg = 'Drop Block Distance: ' + alt_schedule['distance'] + '\n';
    appendCellNote(this.getCellRange(index+2, 'Valid'), msg);
    break;
  }
     
  //Logger.log('Natural Drop: %s, Alt Drop: %s', 
   //          JSON.stringify(natural_schedule), JSON.stringify(alt_schedule));
  
  // Need to fill remaining fields: Drop-off Date, Drop Block, Route Size
  
  var use_alt_block = false;
  
  if(!natural_schedule && alt_schedule)
    use_alt_block = true;
  else if(natural_schedule && alt_schedule) {
    if(alt_schedule.date.getTime() < natural_schedule.date.getTime())
      use_alt_block = true;
  }
  
  Logger.log('Drop Block index: %s, Route Size index: %s',
             hdr.indexOf('Drop Block'), hdr.indexOf('Route Size'));
  
  if(use_alt_block) {
    signup[hdr.indexOf('Drop Date')] = alt_schedule.date;
    signup[hdr.indexOf('Drop Block')] = alt_schedule.name;
    signup[hdr.indexOf('Route Size')] = alt_schedule.booked;
  }
  else {
    signup[hdr.indexOf('Drop Date')] = natural_schedule.date;
    signup[hdr.indexOf('Drop Block')] = natural_schedule.name;
    signup[hdr.indexOf('Route Size')] = natural_schedule.booked;
  }
  
  // Query scheduled Block Size if not on Calendar
  
  if(signup[hdr.indexOf('Route Size')] == '?') {   
    var response = API(
      '/query/route_size',
      this.conf, {
        'category': this.conf['ETAP_QRY_CTGRY'],
        'query':signup[hdr.indexOf('Drop Block')],
        'date':date_to_ddmmyyyy(signup[hdr.indexOf('Drop Date')])});
    
    var booked = response.substring(0, response.indexOf('/'));
    signup[hdr.indexOf('Route Size')] = booked;
  }
  
  // Set Formula to re-calculate Booking Size with all pending signups matching Drop Block
  
  var formula = "="+signup[hdr.indexOf('Route Size')]+"+ countif(C[-1]:C[-1], R[0]C[-1])";
  
  this.wks_fmlas[index][this.wks_hdr.indexOf('Route Size')] = formula;
  
  Logger.log('Drop Block found: ' + signup[hdr.indexOf('Drop Block')]);
}

//---------------------------------------------------------------------
Signups.prototype.assignTemporaryNotes = function(index) {
  var signup = this.wks_values[index];
  var hdr = this.wks_hdr;
  
  if(!signup[hdr.indexOf('Drop Date')])
    return false;
  
  signup[hdr.indexOf('Driver Notes')] = 
    '***Dropoff ' + signup[hdr.indexOf('Drop Date')].toDateString() + '***';
  
  if(signup[hdr.indexOf('Drop Block')] != signup[hdr.indexOf('Block')]) {
    signup[hdr.indexOf('Office Notes')] = signup[hdr.indexOf('Office Notes')].replace(/\*{3}RMV\s(B|R)\d{1,2}[a-zA-Z]{1}\*{3}(\n|\r)?/g, '');
    signup[hdr.indexOf('Office Notes')] += '\n***RMV ' + signup[hdr.indexOf('Drop Block')] + '***';
  }
}

//---------------------------------------------------------------------
Signups.prototype.assignBlock = function(index) {
  /* Use Google Maps Geolocator and KML rows to set Residential Block and Area defined 
   * fields. 
   */
  
  var signup = this.wks_values[index];
  var hdr = this.wks_hdr;
  var err_msg = 'Failed to find Block. Reason: ';
  
  // A. Geolocate Address
  
  if(!signup[hdr.indexOf('Address')])
    return false;
  
  var replace_address = true;
  var geo_res = Geo.geocodeBeta(
    signup[hdr.indexOf('Address')], 
    signup[hdr.indexOf('City')], 
    signup[hdr.indexOf('Postal')]);
  
  if(!Geo.hasAddressComponent(geo_res, 'postal_code') || 
     !Geo.hasAddressComponent(geo_res, 'route') || 
     !Geo.hasAddressComponent(geo_res, 'street_number') ||
     !("location" in geo_res.geometry)) {
       
       replace_address = false;
       
       //Logger.log(signup[hdr.indexOf('Validation')] += 'Couldnt validate address. Using approximation.\n\n');
       
       appendCellNote(
         this.getCellRange(index+2, 'Valid'), 
         'Using address approximation "' + geo_res.formatted_address + '"\n');
       
       this.getCellRange(index+2, 'Address').setFontColor(COLOR['light red']);
    }
  
  var postal = null;
  
  for(var j=0; j<geo_res.address_components.length; j++) {
    if(geo_res.address_components[j]['types'].indexOf('postal_code') == -1)
      continue;
    
    postal = geo_res.address_components[j]['short_name'];
    
    if(postal.substring(0,3) != signup[hdr.indexOf('Postal')].substring(0,3)) {
      appendCellNote(
        this.getCellRange(index+2, 'Valid'),
        "Replacing Postal \"" + signup[hdr.indexOf('Postal')] + "\"\n");
    }
  }
 
  // B. Search KML map data to identify Block
  
  var map_title = "";
  
  try {
    map_title = Geo.findMapTitle(
      geo_res.geometry.location.lat, 
      geo_res.geometry.location.lng, 
      this.maps);
  }
  catch(err) {
    //signup[hdr.indexOf('Valid')] += err_msg + " " + err;
    return false;
  }
  
  if(!map_title) {
    //Logger.log(signup[hdr.indexOf('Valid')] += err_msg + "Failed to find KML map");
    return false;
  }
  
  var block = Parser.getBlockFromTitle(map_title);
  
  // C. Get Block Size
  
  var block_size = API(
    '/query/block_size',
    this.conf, {
      'category':this.conf['ETAP_QRY_CTGRY'],
      'query': block});
  
  // D. Find Neighborhood (or neighborhood groupings)
  
  var neighbhd = null;
  var neighbhd_list = map_title.substring(
      map_title.indexOf("[")+1, 
      map_title.indexOf("]")).split(',');
  
  for(var i=0; i<geo_res.address_components.length; i++) {
    if(geo_res.address_components[i].types.indexOf('neighborhood') > -1)
      if(geo_res.address_components[i]['short_name'].indexOf(neighbhd_list) >= 0)
        neighbhd = geo_res.address_components[i]['short_name'];
  }

  if(!neighbhd)
    neighbhd = neighbhd_list.join(',');
  
  var address = signup[hdr.indexOf('Address')];
  
  if(replace_address) {
    if(address != geo_res.formatted_address.substring(0, geo_res.formatted_address.indexOf(','))){
      appendCellNote(
        this.getCellRange(index+2, 'Valid'),
        "Corrected address spelling: \"" + address + "\"\n");   
      address = geo_res.formatted_address.substring(0, geo_res.formatted_address.indexOf(','));
    }
  }
  
  signup[hdr.indexOf('Block')] = block;
  signup[hdr.indexOf('Block Size')] = block_size;
  signup[hdr.indexOf('Area')] = neighbhd;
  signup[hdr.indexOf('Address')] = address;
  signup[hdr.indexOf('Postal')] = postal;
}

//---------------------------------------------------------------------
Signups.prototype.getCellRange = function(row, hdr_name) {
  return this.wks.getRange(row, this.wks_hdr.indexOf(hdr_name)+1);
}

//---------------------------------------------------------------------
Signups.prototype.checkForDuplicates = function(index) {
  /* Check the most recently added form signup for duplicates in eTapestry */
  
  var signup = this.wks_values[index];
  var hdr = this.wks_hdr;

  var criteria = {
    'address': signup[hdr.indexOf('Address')],
    'name': signup[hdr.indexOf('First')] + ' ' + signup[hdr.indexOf('Last')],
  };
   
  if(signup[hdr.indexOf('Email')])
    criteria['email'] = signup[hdr.indexOf('Email')];
}

//---------------------------------------------------------------------
Signups.prototype.validateEmail = function(index) {
  
  var email = this.wks_values[index][this.wks_hdr.indexOf('Email')];
  
  if(!email)
    return;
  
  if(!email.match(/[\w-]+@([\w-]+\.)+[\w-]+/gi)) {
    appendCellNote(
      this.getCellRange(index+2, 'Email'),
      "Invalid Email Address");
    this.getCellRange(index+2, 'Email').setFontColor(COLOR['light red']);
    this.setValid(index, false);
  } 
}

//---------------------------------------------------------------------
Signups.prototype.setValid = function(index, is_valid) {
  
  
  if(is_valid) {
    this.getCellRange(index+2, 'Valid').setFontColor(COLOR['green']);
    this.wks_values[index][this.wks_hdr.indexOf('Valid')] = SYMBOL['checkmark'];
  }
  else {
    this.getCellRange(index+2, 'Valid').setFontColor(COLOR['light red']);
    this.wks_values[index][this.wks_hdr.indexOf('Valid')] = SYMBOL['x'];
  }
}

//---------------------------------------------------------------------
Signups.prototype.validatePhone = function(index) {
  
  var signup = this.wks_values[index];
  var phone = String(signup[this.wks_hdr.indexOf('Landline')]);
  if(!phone)
    return;
  phone = phone.replace(/\D/g,''); // format: ###-###-####
  
  if(phone.length == 10) {
    phone = phone.substring(0,3) + '-' + phone.substring(3,6) + '-' + phone.substring(6,10);
    signup[this.wks_hdr.indexOf('Landline')] = phone;
  }
    
  var rv;
  try {
    rv = UrlFetchApp.fetch(
      'https://lookups.twilio.com/v1/PhoneNumbers/' + phone + '?Type=carrier', {
        "method": "GET",
        "muteHttpExceptions": true,
        "headers":{
          "Authorization": "Basic " + Utilities.base64Encode(this.conf['TWILIO_API_KEY'])}});
  }
  catch(e) {
    Logger.log(e);
    return false;
  }
  
  var result = JSON.parse(rv);
  Logger.log(result);

  if(!result.hasOwnProperty("carrier")) {
    Logger.log("Invalid phone");
    appendCellNote(
      this.getCellRange(index+2, "Landline"),
      "Invalid Phone Number " + phone);
    this.getCellRange(index+2, 'Landline').setFontColor(COLOR['light red']);
    this.setValid(index, false);

  }
  else if(result['carrier']['type'] == 'mobile') {
    signup[this.wks_hdr.indexOf('Mobile')] = phone;
    signup[this.wks_hdr.indexOf('Landline')] = '';
  }
}

//---------------------------------------------------------------------
Signups.prototype.buildPayload = function(ui) {
  /* Send 'em to eTapestry via Bravo */
  
  var request_id = new Date().getTime();
  var payload = [];
  var hdr = this.wks_hdr;
  
  // Select signups which have been audited but not yet uploaded,
  // have all required fields
  for(var i=0; i<this.wks_values.length; i++) {
    var signup = this.wks_values[i];
    if(!signup[hdr.indexOf('Audit')])
      continue;
    if(signup[hdr.indexOf('Upload')])
      continue;
    if(!signup[hdr.indexOf('Drop Date')])
      continue;
    if(!signup[hdr.indexOf('Block')])
      continue;
    if(!signup[hdr.indexOf('Drop Block')])
      continue;
    if(!signup[hdr.indexOf('Area')])
      continue;
    
    var blk = signup[hdr.indexOf('Block')];
    var drop_blk = signup[hdr.indexOf('Drop Block')];
    var drop_note = "***"+signup[hdr.indexOf("Drop Notes")]+"***";
    var off_note = signup[hdr.indexOf("Office Notes")];
    var drv_note = signup[hdr.indexOf("Driver Notes")];
    
    var udf = {
      'Status': signup[hdr.indexOf('Status')],
      'Signup Date': date_to_ddmmyyyy(signup[hdr.indexOf('Date')]),
      'Dropoff Date': date_to_ddmmyyyy(signup[hdr.indexOf('Drop Date')]),
      'Next Pickup Date': date_to_ddmmyyyy(signup[hdr.indexOf('Drop Date')]),
      'Neighborhood': signup[hdr.indexOf('Area')].split(", ").join(","),
      'Block': (drop_blk == blk ? blk.split(", ").join(",") : (blk+","+drop_blk).split(", ").join(",")),
      'Driver Notes': (drv_note ? drop_note+'\n'+drv_note : drop_note),
      'Office Notes': (drop_blk == blk ? off_note: off_note + '***RMV '+drop_blk+'***'),
      'Tax Receipt': signup[hdr.indexOf('Receipt')],
      'Reason Joined': signup[hdr.indexOf('Reason')],
      'Referrer': signup[hdr.indexOf('Referrer')],
     };
    
    if(hdr.indexOf('Mailing Status') > -1)
      udf['Mailing Status'] = signup[hdr.indexOf('Mailing Status')];
    
    if(signup[hdr.indexOf('Mobile')]) {
      // Make into "+14031234567" format
      udf['SMS'] = "+1" + signup[hdr.indexOf('Mobile')].replace(/\-|\(|\)|\s/g, "");
    }
    
    var persona = {
      'personaType': signup[hdr.indexOf('Persona Type')],
      'address': signup[hdr.indexOf('Address')],
      'city': signup[hdr.indexOf('City')],
      'state': 'AB',
      'country': 'CA',
      'postalCode': signup[hdr.indexOf('Postal')],
      'email': signup[hdr.indexOf('Email')],
      'phones': [
        {'type': 'Voice', 'number': signup[hdr.indexOf('Landline')]},
        {'type': 'Mobile', 'number': signup[hdr.indexOf('Mobile')]}
      ]
    };
    
    if(signup[this.wks_hdr.indexOf('Name Format')] == 'Individual') {
      persona['nameFormat'] = 1;
      persona['name'] = signup[hdr.indexOf('First')] + ' ' + 
        signup[hdr.indexOf('Last')];
      persona['sortName'] = signup[hdr.indexOf('Last')] + ', ' + 
        signup[hdr.indexOf('First')];
      persona['firstName'] = signup[hdr.indexOf('First')];
      persona['lastName'] = signup[hdr.indexOf('Last')];
      persona['shortSalutation'] = signup[hdr.indexOf('First')];
      persona['longSalutation'] = signup[hdr.indexOf('First')] + ' ' + 
        signup[hdr.indexOf('Last')];
      persona['envelopeSalutation'] = (signup[hdr.indexOf('Title')] || '') + ' ' + 
        signup[hdr.indexOf('First')] + ' ' + signup[hdr.indexOf('Last')];
    }
    else {
      persona['nameFormat'] = 3;
      persona['name'] = signup[hdr.indexOf('Business Name')];
      persona['sortName'] = persona['name'];
      udf['Contact'] = signup[hdr.indexOf('Contact Person')];
    }    
    
    payload.push({
      'ss_row': i+2,
      'existing_account': signup[hdr.indexOf('Existing Account')],
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
