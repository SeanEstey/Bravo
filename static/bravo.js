//---------------------------------------------------------------
String.prototype.toTitleCase = function(n) {
   var s = this;
   if (1 !== n) s = s.toLowerCase();
   s = s.replace(/_/g, ' ');
   return s.replace(/\b[a-z]/g,function(f){return f.toUpperCase()});
}

//---------------------------------------------------------------
function addBravoTooltip() {
  $(document).tooltip({
    position: {
      my: 'center bottom-20',
      at: 'center top',
      using: function(position, feedback) {
        $(this).css(position);
        $('<div>')
          .addClass('arrow')
          .addClass(feedback.vertical)
          .addClass(feedback.horizontal)
          .appendTo(this);
      }
    }
  });
}

//---------------------------------------------------------------
function useJQueryBtn() {
  $("input[type=submit], button")
    .button()
    .click(function( event ) {
      event.preventDefault();
    });
}

//---------------------------------------------------------------
function getPlivoAccount() {
  var request =  $.ajax({
      type: 'GET',
      url: 'http://23.239.21.165:5000/account'
    });

  request.done(function(msg){
    $('#account').html('Balance: ' + msg);
    console.log('account: ' + JSON.stringify(msg));
  });

}

//---------------------------------------------------------------
function getCeleryStatus() {
  var request =  $.ajax({
      type: 'GET',
      url: 'http://23.239.21.165:5000/celery_status'
    });

  request.done(function(msg){
    $('#status').html('Status: ' + msg);
    console.log('celery status: ' + JSON.stringify(msg));
  });
}

//---------------------------------------------------------------
// Error/confirmation dialog UI for all views
function showDialog($element, msg, _title, _buttons) {
  if(typeof(_buttons) === 'undefined') {
      _buttons = [{ 
        text: "Sorry, I'll fix it", 
        click: function() { $( this ).dialog( "close" ); }
      }];
  }

  if(typeof(_title) === 'undefined') {
    _title = 'What have you done??'
  }

  var dialog_style = { 
    modal: true,
    title: _title,
    dialogClass: 'ui-dialog-osx',
    width: 500,
    height: 'auto',
    buttons: _buttons,
    show: { effect: 'fade', duration:150},
    hide: { effect: 'fade', duration:150}
  };
  
  // MUST have a <p> element for the msg
  $element.find($('p')).html(msg);
  $element.dialog(dialog_style);
}

//---------------------------------------------------------------
// View: new_job
function initNewJobView() {
  useJQueryBtn();
  addBravoTooltip();
  $('#datepicker').datepicker();
  $("input[type=file]").nicefileinput();
  onSelectTemplate();
  updateFilePickerTooltip();
  $submit_btn = $('#submit_btn');
  $submit_btn.click(function(){
    validateNewJobForm();
  });
  $('body').css('display','block');
}

//---------------------------------------------------------------
// View: new_job
function updateFilePickerTooltip() {
  var $select = $('#template-select');
  var $template = $select.find($('option:selected'));
  var request = $.ajax({
    type: 'GET',
    url: 'http://23.239.21.165:5000/get/template/' + $template.attr('value')
  });
  request.done(function(msg){
    var title = 'Upload a .CSV file with columns ';
    $('#call-list-div').attr('title', title + msg); 
  });
}

//---------------------------------------------------------------
// View: new_job
function onSelectTemplate() {
  var $select = $('#template-select');
  $select.change(function(){
    var $template = $select.find($('option:selected'));
    console.log($template.text());
    updateFilePickerTooltip();
    if($template.text() == 'Empties to Winn Reminder') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
    }
    else if($template.text() == 'Special Message') {
      $('#special_msg_div').show();
      $('#order_div').show();
    }
    else if($template.text() == 'Green Goods Delivery') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
    }
    else if($template.text() == 'Empties to Winn Followup') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
    }
  });
}

//---------------------------------------------------------------
// View: new_job
function validateNewJobForm() {
  var paramObj = {};
  $.each($('form').serializeArray(), function(_, kv) {
    paramObj[kv.name] = kv.value;
  }); 

  // Validate form data
  var missing = [];
  var filename = $('#call-list-div').val();
  var expired_date = false;
  var invalid_date = false;
  var wrong_filetype = false;
  var scheduled_date = null;
  
  if(!filename)
    missing.push('CSV File');
  else if(filename.indexOf('.csv') <= 0)
    wrong_filetype = true;
  if(!paramObj['time'])
    missing.push('Schedule Time');
  if(!paramObj['date'])
    missing.push('Schedule Date');
  else {
    var now = new Date();
    var date_str = paramObj['date'];
    if(paramObj['time'])
      date_str += ', ' + paramObj['time'];
    // Datejs for parsing strings like '12pm'
    scheduled_date = Date.parse(date_str);
    if(!scheduled_date)
      invalid_date = true;
    else if(scheduled_date.getTime() < now.getTime())
      expired_date = true;
  }
  if(paramObj['template'] == 'special_msg') {
    if(!paramObj['message'])
      missing.push('Special Message');
  }

  var msg = ''; 
  if(missing.length > 0) {
    msg = 'You forgot to enter: ';
    msg += '<b>' + missing.join(', ') + '</b><br><br>';
  }
  if(wrong_filetype)
    msg += 'The file you selected is not a .CSV';

  if(missing.length > 0 || wrong_filetype) {
    showDialog($('#dialog'), msg);
  }
  else if(expired_date) {
    msg = 'The scheduled date is before the present:<br><br>' + 
    '<b>' + scheduled_date.toString('dddd, MMMM d, yyyy @ hh:mm tt') + 
    '</b><br><br>' +
    'Do you want to start this job now?';

    var buttons = [
      { text: "No, let me fix it", 
        click: function() { $( this ).dialog( "close" ); }}, 
      { text: 'Yes, start job now', 
        click: function() { $(this).dialog('close'); $('form').submit();}}
    ];
    showDialog($('#dialog'), msg, null, buttons);
  }
  else if(invalid_date) {
    msg = 'Could not understand the date and time provided. Please correct.';
    showDialog($('#dialog'), msg);
  }
  else {
    $('form').submit(); 
  }
}

//---------------------------------------------------------------
// View: show_calls
function initShowCallsView() {
  $('.delete-btn').button({
    icons: {
      primary: 'ui-icon-trash'
    },
    text: false
  })

  $('.call_status_td').each(function() {
    var string = $(this).html().toTitleCase();
    $(this).html(string);
  });
  $('.call_msg_td').each(function() {
    var string = $(this).html().toTitleCase();
    $(this).html(string);
  });
  $('.call_date_td').each(function() {
    var date = Date.parse($(this).html());
    var string = date.toDateString();
    $(this).html(string);
  });

  $('.delete-btn').each(function(){ 
    $(this).click(function(){
      msg = 'Are you sure you want to cancel this call?';
      url = $(this).attr('id');
      console.log('prompt to delete' + url);
      var buttons = [
        { text: "No", 
          click: function() { $( this ).dialog( "close" ); }}, 
        { text: 'Yes', 
          click: function() { $(this).dialog('close'); $(location).attr('href',url);}}
      ];
      showDialog($('#dialog'), msg, 'Confirm Action', buttons);
    });
  });

  if($('#timer').text().indexOf('Pending') > 0)
    beginCountdown($('#timer'), $('#scheduled_datetime').text());

  $('body').css('display','block');

  makeCallFieldsClickable();
  
  // Init SocketIO
  var socket = io.connect('http://' + document.domain + ':' + location.port);
  socket.on('connect', function(){
    socket.emit('connected');
  });
  socket.on('update_msg', function(data) {
    receiveMsgUpdate(data);
  });
  socket.on('update_job', function(data) {
    receiveJobUpdate(data);
  });
}

//---------------------------------------------------------------
// View: show_calls
function makeCallFieldsClickable() {
  $("td").on('click',function() {      
    $cell = $(this);
    // Editable fields are assigned 'name' attribute
    var name = $cell.attr('name');
    if(!name)
      return;
    if($('#timer').text().indexOf('Pending') < 0)
      return;
    if(name == 'status' || name == 'message' || name == 'attempts')
      return;
    if($cell.find('input').length > 0)
      return;

    // Insert <input> element into <td> to enable edits
    var row_id = $cell.parent().attr('id');
    var text = $cell.text();
    var width = $cell.width()*.90;
    $cell.html("<input type='text' value='" + text + "'>");
    var $input = $cell.find('input');
    $input.width(width);
    $input.css('font-size', '16px');
  
    // Save edit to DB when focus lost, remove <input> element 
    $input.blur(function() {
      $cell.html($input.val());
      var call_id = $cell.parent().attr('id');
      var field_name = $cell.attr('name');
      console.log('field_name: ' + field_name);
      var field_value = $input.val();

      var payload = {}
      payload[field_name] = field_value
      
      $.ajax({
        type: 'POST',
        url: 'http://23.239.21.165:5000/edit/call/' + call_id,
        data: payload
      });
    });
    
    $input.focus();
  });
}

//---------------------------------------------------------------
function receiveJobUpdate(socket_data) {
  if(socket_data['status'] == 'complete') {
    console.log('job complete!');
    $('#timer').text('Complete');
  }
}

//---------------------------------------------------------------
// View: show_calls
function receiveMsgUpdate(socket_data) {
  // Clear the countdown timer if it is running
  if(window.countdown_id) {
    clearInterval(window.countdown_id);
    $('#timer').text('In Progress');
  }

  console.log('received update: ' + JSON.stringify(socket_data));
  // Find matching row_id to update
  var $row = $('#'+socket_data['id']);
  if('status' in socket_data) {
    code = toTitleCase(socket_data['status']);
    $row.find('[name="status"]').html(code);
  }
  if('code' in socket_data) {
    code = socket_data['code'];
    if(code == 'NORMAL_TEMPORARY_FAILURE')
      code = 'Not in Service';
    else
      code = toTitleCase(code);
    $row.find('[name="message"]').html(code);
  }
  if('attempts' in socket_data)
    $row.find('[name="attempts"]').html(socket_data['attempts']);
  if('office_notes' in socket_data)
    $row.find('[name="office_notes"]').html(socket_data['office_notes']);
}

//---------------------------------------------------------------
// View: show_calls
// Display timer counting down until event_datetime
function beginCountdown($timer, event_datetime) {
  var scheduled = Date.parse(event_datetime);
  
  window.countdown_id = setInterval(function() {
    var today = new Date();
    var diff_ms = scheduled.getTime() - today.getTime();

    if(diff_ms < 0) {
      $timer.text('Completed');
      return;
    }

    var diff_days = diff_ms / (1000 * 3600 * 24);
    var diff_hrs = ((diff_days + 1) % 1) * 24;
    var diff_min = ((diff_hrs + 1) % 1) * 60;
    var diff_sec = ((diff_min + 1) % 1) * 60;
    
    $timer.text(
      'Pending: ' + Math.floor(diff_days) + ' Days ' + 
      Math.floor(diff_hrs) + ' Hours ' + 
      Math.floor(diff_min) + ' Min ' + 
      Math.floor(diff_sec) + ' Sec');

  }, 1000);
}




//---------------------------------------------------------------
// View: show_jobs
function initShowJobs() {
  addBravoTooltip();

  $('.delete-btn').button({
    icons: {
      primary: 'ui-icon-trash'
    },
    text: false
  })
  $('.delete-btn').addClass('redButton');

  $('.delete-btn').each(function(){ 
    $(this).click(function(){
      msg = 'Are you sure you want to cancel this job?';
      url = $(this).attr('id');
      console.log('prompt to delete' + url);
      var buttons = [
        { text: "No", 
          click: function() { $( this ).dialog( "close" ); }}, 
        { text: 'Yes', 
          click: function() { $(this).dialog('close'); $(location).attr('href',url);}}
      ];
      showDialog($('#dialog'), msg, 'Confirm Action', buttons);
    });
  });

  $('body').css('display','block');
}
