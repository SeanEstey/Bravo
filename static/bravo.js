//---------------------------------------------------------------
function useJQueryBtn() {
  $("input[type=submit], button")
    .button()
    .click(function( event ) {
      event.preventDefault();
    });
}

//---------------------------------------------------------------
function onSelectTemplate() {
  var $select = $('#template-select');
  $select.change(function(){
    var $template = $select.find($('option:selected'));
    console.log($template.text());

    if($template.text() == 'Empties to Winn Reminder') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
    else if($template.text() == 'Special Message') {
      $('#special_msg_div').show();
      $('#order_div').show();
      $('#recorded_msg_div').show();
      $('#verify_phone_div').show();
    }
    else if($template.text() == 'Green Goods Delivery') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
    else if($template.text() == 'Empties to Winn Followup') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
  });
}

//---------------------------------------------------------------
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
function validateNewJobForm() {
  var paramObj = {};
  $.each($('form').serializeArray(), function(_, kv) {
    paramObj[kv.name] = kv.value;
  }); 

  // Validate form data
  var missing = [];
  var filename = $('#call-list-div').val();
  var wrong_date = false;
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
    console.log(scheduled_date.toString());
    if(scheduled_date.getTime() < now.getTime())
      wrong_date = true;
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
  else if(wrong_date) {
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
  else {
    $('form').submit(); 
  }
}

//---------------------------------------------------------------
function initNewJob() {
  useJQueryBtn();
  $('#datepicker').datepicker();
  $("input[type=file]").nicefileinput();
  onSelectTemplate();
  $submit_btn = $('#submit_btn');
  $submit_btn.click(function(){
    validateNewJobForm();
  });
  $('body').css('display','block');
}


//---------------------------------------------------------------
function initShowCalls() {
  $('.delete-btn').button({
    icons: {
      primary: 'ui-icon-trash'
    },
    text: false
  })

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

  // Display countdown if job status == Pending
  if($('#timer').text().indexOf('Pending') > 0) {
    var scheduled = Date.parse($('#scheduled_datetime').text());
    setInterval(function() {
      var today = new Date();
      var diff_ms = scheduled.getTime() - today.getTime();

      if(diff_ms < 0) {
        $('#timer').text('Completed');
        return;
      }

      var diff_days = diff_ms / (1000 * 3600 * 24);
      var diff_hrs = ((diff_days + 1) % 1) * 24;
      var diff_min = ((diff_hrs + 1) % 1) * 60;
      var diff_sec = ((diff_min + 1) % 1) * 60;
      $('#timer').text('Pending: ' + Math.floor(diff_days) + ' Days ' + Math.floor(diff_hrs) + ' Hours ' + Math.floor(diff_min) + ' Min ' + Math.floor(diff_sec) + ' Sec')
    }, 1000);
  }

  $('body').css('display','block');

  $("td").on('click',function() {      
    // Editable fields are assigned 'name' attribute
    var name = $(this).attr('name');
    if(!name)
      return;
  
    if($('#timer').text().indexOf('Pending') < 0)
      return;

    if(name != 'status' && name != 'message' && 'attempts') {
      var row_id = $(this).parent().attr('id');
      processCellClick(row_id, $(this));
    }
  });

  // Init SocketIO
  var socket = io.connect('http://' + document.domain + ':' + location.port);
  
  socket.on('connect', function() {
    console.log('socket.io connected');
    socket.emit('connected');
    socket.on('disconnect', function() {
      console.log('socket.io disconnected');
      socket.emit('disconnected');
    });
  });
  
  socket.on('update', function(data) {
    console.log('received update:: ' + JSON.stringify(data));
    // Find matching row_id to update
    var $row = $('#'+data['id']);
    $row.find('[name="status"]').html(data['status']);
    $row.find('[name="message"]').html(data['message']);
    $row.find('[name="attempts"]').html(data['attempts']);
    $('#timer').text('In Progress');
  });
}

//---------------------------------------------------------------
// Clicking on table cell allows edits which are saved to DB
function processCellClick(row_id, $cell) {
  if($cell.find('input').length == 0) {
    // Enable cell edit
    var text = $cell.text();
    var width = $cell.width()*.90;
    $cell.html("<input type='text' value='" + text + "'>");
    var $input = $cell.find('input');
    $input.width(width);
    $input.css('font-size', '16px');
   
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
  }
}

//---------------------------------------------------------------
function initShowJobs() {
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
