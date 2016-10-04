
  //---------------------------------------------------------------------
  window.onload = function(){
  };
  
  //---------------------------------------------------------------------
  function validate(field_id) {
    var element = document.getElementById(field_id);  
    
    // Some browsers (Safari) do not evaluate <input pattern> property. 
    // Manually test regular expression
    if(element.pattern) {
      var pattern = new RegExp(element.pattern);
      
      if(!pattern.test(element.value)) {
        element.style.border = '1px solid red';
        element.value = '';
        element.placeholder = 'Invalid value';
        return false;
      }
    }
 
    return true;
  }

  //---------------------------------------------------------------------
  function search(my_form) {  
    var search_value = my_form.elements['search_box'].value;
    
    my_form.elements['search_box'].value = '';
    
    if(!search_value) {
      return false;
    }

    document.getElementById('results').innerHTML = '';
    
    document.getElementById('status_lbl').innerHTML = 'Searching...';

    console.log('Starting search for: ' + search_value);
    
    google.script.run
      .withSuccessHandler(onSearchSuccess)
      .withFailureHandler(onSearchFailure)
      .search(search_value);
  }
  
  //---------------------------------------------------------------------
  function onSearchSuccess(response) { 
    response = JSON.parse(response);
    
    if(response['status'] == 'failed') {
      document.getElementById('status_lbl').style.display = 'block';
      document.getElementById('status_lbl').innerHTML = response['message'];
      return false;
    }
    
    if(response['booking_results']) {   
      var results = response['booking_results'];
      
      console.log(results.length + ' search results returned');
       
      if(response['account_name']) {
        document.getElementById('account_id').value = response['account_id'];
        document.getElementById('status_lbl').innerHTML = response['message'];
      }
      else {
        document.getElementById('status_lbl').innerHTML = response['message'];
      }
      
      document.getElementById('search_box').value = '';
      
      var html = 
        "<table style='margin:15px auto;'>" +
        "<tr><th style='text-align:center;'>Date</th><th>Route</th><th style='text-align:center;'>Area</th><th style='text-align:center;'>Postal Codes</th><th>Booked</th><th>Max</th><th>Distance</th></tr>";
        
      if(results.length == 0) {
        
      }
   
      for(var i=0; i<results.length; i++) {
        var date = new Date(results[i]['date']);
        
        var block = results[i]['event_name'].substring(0, results[i]['event_name'].indexOf(' '));
        var area = results[i]['event_name'].slice(results[i]['event_name'].indexOf('[')+1, results[i]['event_name'].indexOf(']'));
        
        if(!results[i]['distance'])
          results[i]['distance'] = 'n/a';
      
        html +=
          "<tr style='padding:5px 10px;'>" +
          "<td style='text-align:left; width:20%; padding:0 25px'>" + date.toDateString() + "</td>" +
          "<td style='padding:0 25px; text-align:right'>" + block + "</td>" +
          "<td style='padding:0 25px; text-align:right'>" + area + "</td>" +
          "<td style='width:50px; padding:0 25px; text-align:right'>" + results[i]['location'] + "</td>" +
          "<td style='padding:0 25px'>" + results[i]['booking_size'] + "</td>" +
          "<td style='padding:0 25px'>" + results[i]['max_size'] + "</td>" +
          "<td style='padding:0 25px'>" + results[i]['distance'] + "</td>";
          
        if(results[i]['booking_size'] >= results[i]['max_size'])
          html += "<td><input style='color:red;' type='button' name='' class='button' value='Full' onclick='makeBooking(this)'/></td></tr>";
        else
          html += "<td><input style='color:green;' type='button' name='' class='button' value='Book' onclick='makeBooking(this)'/></td></tr>";
      }
      
      html += "</table>";
      document.getElementById('results').insertAdjacentHTML('beforeend', html);
      
      return true;
    }
  }
  
  //---------------------------------------------------------------------
  function onSearchFailure(result) {
    console.log('failure! result: ' + result);
    document.getElementById('status_lbl').innerHTML = result;
  }
  
  //---------------------------------------------------------------------
  function makeBooking(btn) {
    var tr = btn.parentNode.parentNode;
    var date_str = tr.children[0].innerHTML;
    var block = tr.children[1].innerHTML;
    
    document.getElementById('results').style.display = 'none';
    document.getElementById('booking_options').style.display = 'block';
    document.getElementById('search_row').style.display = 'none';
    
    document.getElementById('booking_block').value = block;
    document.getElementById('booking_date').value = date_str;
    
    // Do we have an account yet? If not, ask user to enter
    if(!document.getElementById('account_id').value) {
      document.getElementById('status_lbl').innerHTML = 'Booking onto Block <b>' + block + '</b>. Enter Account Number and any special driver instructions';
      document.getElementById('account_id_div').style.display = 'block';
    }
    else
      document.getElementById('status_lbl').innerHTML = 'Booking account <b>'+ document.getElementById('account_id').value + '</b> onto Block <b>' + block + '</b>. Enter any special driver instructions';
  }
  
  //---------------------------------------------------------------------
  function onBookingSuccess(response) {
    document.getElementById('status_lbl').innerHTML = response;
  }
  
  //---------------------------------------------------------------------
  function onBookingFailure(response) {
    var results_div = document.getElementById('results');
    results_div.innerHTML = response;
  }
  
  //---------------------------------------------------------------------
  function searchKeyPress(e) {
    // look for window.event in case event isn't passed in
    e = e || window.event;
    if (e.keyCode == 13) {
      document.getElementById('find_btn').click();
      return false;
    }
    return true;
  }
  
  //---------------------------------------------------------------------
  function form_submit(my_form) {  
    for(var i=0; i<my_form.elements.length; i++) {
      if(my_form.elements[i].required && !my_form.elements[i].value) {
        console.log('Missing form value for field ' + my_form.elements[i].name);
        return false;
      }
    }
    
    var book_date = my_form.elements['booking_date'].value;
    var extra_driver_notes = my_form.elements['driver_notes'].value;
 
    var udf = {
      'Block': my_form.elements['booking_block'].value,
      'Office Notes': '***RMV '+ my_form.elements['booking_block'].value + '***'
    };
    
    var booking_type = my_form.elements['booking_type'].value;
    
    if(booking_type == 'pickup') {
      udf['Next Pickup Date'] = date_to_ddmmyyyy(new Date(book_date));
      udf['Driver Notes'] = '***'+ book_date +': Pickup Needed. ' + extra_driver_notes + '***';
    }
    else if(booking_type == 'delivery') {
      udf['Next Delivery Date'] = date_to_ddmmyyyy(new Date(book_date));
      udf['Driver Notes'] = '***'+ book_date +': Delivery. ' + extra_driver_notes + '***';
    }
    
    var account_id = my_form.elements['account_id'].value;
    
     // Hide everything
    document.getElementById('booking_options').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('status_lbl').innerHTML = 'Attempting to make booking...';
    
    console.log('attempting ' + booking_type + ' for account ' + account_id + ', udf: ' + JSON.stringify(udf));
    
    google.script.run
      .withSuccessHandler(onBookingSuccess)
      .withFailureHandler(onBookingFailure)
      .makeBooking(account_id, udf, booking_type);  
      
   }
   
   
  //---------------------------------------------------------------------
  // Used to convert to eTapestry date format
  function date_to_ddmmyyyy(date) {
    if(!date)
      return;
  
    var day = date.getDate();
    if(day < 10)
      day = '0' + String(day);
  
    var month = date.getMonth() + 1;
    if(month < 10)
      month = '0' + String(month);
  
    return day + '/' + month + '/' + String(date.getFullYear());
  }
  
