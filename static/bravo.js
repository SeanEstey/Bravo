// Returns decimal code for special HTML characters
function HTMLEncode(str) {
  var i = str.length,
    aRet = [];

  while (i--) {
    var iC = str[i].charCodeAt();
    if (iC < 65 || iC > 127 || (iC > 90 && iC < 97)) {
      aRet[i] = '&#' + iC + ';';
    } else {
      aRet[i] = str[i];
    }
  }
  return aRet.join('');
}

String.prototype.toTitleCase = function(n) {
   var s = this;
   if (1 !== n) s = s.toLowerCase();
   s = s.replace(/_/g, ' ');
   return s.replace(/\b[a-z]/g,function(f){return f.toUpperCase()});
}

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

function useJQueryBtn() {
  $("input[type=submit], button")
    .button()
    .click(function( event ) {
      event.preventDefault();
    });
}

function getServerStatus(variable) {
  var request =  $.ajax({
      type: 'GET',
      url: $SCRIPT_ROOT + '/get/' + variable
    });

  request.done(function(msg){
    console.log(msg);
  });
}

function displayServerStatus(route, label, $element) {
  var request =  $.ajax({
      type: 'GET',
      url: $SCRIPT_ROOT + route
    });

  request.done(function(msg){
    $element.html(label + ': ' + msg.toTitleCase());
  });
}

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

// View: new_job
function updateFilePickerTooltip() {
  var $select = $('#template-select');
  var $template = $select.find($('option:selected'));
  var request = $.ajax({
    type: 'GET',
    url: $SCRIPT_ROOT + '/get/template/' + $template.attr('value')
  });
  request.done(function(msg){
    var title = 'Upload a .CSV file with columns ';
    $('#call-list-div').attr('title', title + msg); 
  });
}

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

// View: show_calls
function initShowCallsView() {
  var up_arrow = '&#8593;';
  var down_arrow = '&#8595;';
  var $a_child = $('th:first-child a');
  $a_child.html($a_child.html()+down_arrow);
  addBravoTooltip();
  makeCallFieldsClickable();

  // Enable column sorting
  $('th').each(function(){
    var $a = $('a', $(this));
    var encoded_text = HTMLEncode($a.text());
    if(encoded_text.indexOf(down_arrow) > 0)
      $a.attr('title', 'Sort Descending Order');
    else  
      $a.attr('title', 'Sort Ascending Order');

    $a.click(function() {
      var id = $(this).parent().attr('id');
      var sort_col = id.split('col')[1];
      sortCalls($('#show-calls-table'), sort_col);
      var encoded_text = HTMLEncode($(this).text());
      if(encoded_text.indexOf(down_arrow) > 0)
        $(this).attr('title', 'Sort Descending Order');
      else
        $(this).attr('title', 'Sort Ascending Order');
      });
  });

  $('[name="call_status"]').each(function() {
    formatCallStatus($(this), $(this).text());
  });
  
  $('[name="event_date"]').each(function() {
    var date = Date.parse($(this).html());
    var string = date.toDateString();
    $(this).html(string);
  });

  // Display delete call buttons if job status == PENDING
  if($('#job-status').text().indexOf('Pending') >= 0) {
    var args =  window.location.pathname.split('/');
    var job_uuid = args.slice(-1)[0];
    $('.delete-btn').each(function(){ 
      $(this).button({
      icons: {
        primary: 'ui-icon-trash'
      },
      text: false
    })
      $(this).click(function(){
        msg = 'Are you sure you want to cancel this call?';
        call_uuid = $(this).attr('id');
        var $tr = $(this).parent().parent();
        var buttons = [
          { text: "No", 
            click: function() { $( this ).dialog( "close" ); }}, 
          { text: 'Yes', 
            click: function() { 
              $(this).dialog('close');
              var request =  $.ajax({
                type: 'POST',
                url: $SCRIPT_ROOT + '/cancel/call',
                data: {
                  'call_uuid':call_uuid,
                  'job_uuid':job_uuid
              }});
              request.done(function(msg){
                if(msg == 'OK')
                  $tr.remove();});
        }}];
        showDialog($('#dialog'), msg, 'Confirm Action', buttons);
      });
    });
  }
  else {
    $('.delete-btn').hide();
  }

  if($('#timer').text().indexOf('Pending') > 0) {
    updateCountdown();
    window.countdown_id = setInterval(updateCountdown, 1000);
  }

  showJobSummary();
  
  $('body').css('display','block');

  // Init socket.io
  var socketio_url = 'http://' + document.domain + ':' + location.port;
  console.log('attempting socket.io connection to ' + socketio_url + '...');
  var socket = io.connect(socketio_url);
  socket.on('msg', function(msg) {
    console.log('received msg: ' + msg);
  });
  socket.on('connect', function(){
    socket.emit('connected');
    console.log('socket.io connected!');
  });
  socket.on('update_call', function(data) {
    receiveCallUpdate(data);
  });
  socket.on('update_job', function(data) {
    receiveJobUpdate(data);
  });

  // Show only on test server
  if(location.port == 8080) {
    var args =  window.location.pathname.split('/');
    var job_uuid = args.slice(-1)[0];
    $('#execute-job').click(function() {
      var url = $SCRIPT_ROOT + '/request/execute/' + job_uuid;
      console.log('execute_job url: ' + url);
      var request =  $.ajax({
        type: 'GET',
        url: url
      });
    });
    $('#reset-job').click(function() {
      var request =  $.ajax({
        type: 'GET',
        url: $SCRIPT_ROOT + '/reset/' + job_uuid
      });
    });
    $('#dump').attr('href', $SCRIPT_ROOT + '/summarize/' + String(job_uuid));
  }
  else {
    $('#execute-job').hide();
    $('#reset-job').hide();
    $('#dump').hide();
  }
}

// View: show_calls
function formatCallStatus($cell, text) {
  text = text.toTitleCase();
  console.log('formatcallstatus text='+text);
  if(text.indexOf('Sent') >= 0)
    $cell.css({'color':'#009900'});
  else if(text.indexOf('No-Answer') >= 0 || text.indexOf('Busy') >= 0 || text.indexOf('Not In Service') >= 0)
    $cell.css({'color':'#C00000' });
  else
    $cell.css({'color':'#365766'});

  $cell.html(text);
}

// View: show_calls
function sortCalls(table, column) {
  var up_arrow = '&#8593;';
  var down_arrow = '&#8595;';
  var space = '&#32;';
  var tbody = table.find('tbody');

  var $th = $('th:nth-child(' + column + ')');
  var is_ascending = HTMLEncode($th.text()).indexOf(down_arrow) > 0;
  if(is_ascending)
    var sort_by = 'descending';
  else
    var sort_by = 'ascending';
   
  // Clear existing sort arrows 
  $('th a').each(function () {
    var html = HTMLEncode($(this).text());
    html = html.replace(up_arrow, '').replace(down_arrow, '').replace(space, ' ');
    $(this).text(html);
  });

  // Add sort arrow
  var $a = $('a', $th);
  if (sort_by == 'ascending')
    $a.html($a.html() + down_arrow);
  else 
    $a.html($a.html() + up_arrow);

  // Sort rows
  tbody.find('tr').sort(function (a, b) {
    var nth_child = 'td:nth-child(' + column + ')';
    if (sort_by == 'ascending') {
      return $(nth_child, a).text().localeCompare($(nth_child, b).text());
    } else {
      return $(nth_child, b).text().localeCompare($(nth_child, a).text());
    }
  }).appendTo(tbody);
}

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
    if(name == 'message' || name == 'attempts')
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
      var field_name = String($cell.attr('name'));
      console.log(field_name + ' edited');
      var payload = {};
      payload[field_name] = $input.val();
      console.log(payload);
      var request = $.ajax({
        type: 'POST',
        url: $SCRIPT_ROOT + '/edit/call/' + $cell.parent().attr('id'),
        data: payload
      });
      request.done(function(msg){
        if(msg != 'OK') {
          showDialog($('#dialog'), 'Your edit failed. Please enter a correct value: ' + msg);
          $cell.html(text);
        }
      });
    });
    $input.focus();
  });
}

function showJobSummary() {
  console.log('job summary called');
  if($('#job-status').text().indexOf('Completed') >= 0) {
    var sum = 0;
    var n_sent = 0;
    var n_incomplete = 0;
    $('[name="call_status"]').each(function() {
      sum++;
      if($(this).text().indexOf('Sent') >= 0)
        n_sent++;
      else
        n_incomplete++;
    });

    var delivered_percent = Math.floor((n_sent / sum) * 100);
    $('#job-summary').css({'color':'#009900'});
    var text = String(delivered_percent) + '% delivered';
    $('#job-summary').text(text);
  }
}

function receiveJobUpdate(socket_data) {
  console.log('received update: ' + JSON.stringify(socket_data));
  if(socket_data['status'] == 'completed') {
    console.log('job complete!');
    $('#job-status').text('Completed');
    showJobSummary();
    $('.delete-btn').hide();
  }
}

// View: show_calls
function receiveCallUpdate(socket_data) {
  // Clear the countdown timer if it is running
  if(window.countdown_id) {
    clearInterval(window.countdown_id);
    $('#timer').text('In Progress');
  }

  if(typeof socket_data == 'string')
    socket_data = JSON.parse(socket_data);

  console.log('received update: ' + JSON.stringify(socket_data));
  // Find matching row_id to update
  var $row = $('#'+socket_data['id']);
  if('call_status' in socket_data) {
    $cell = $row.find('[name="call_status"]');
    var caption = socket_data['call_status'];
    if(socket_data['call_status'] == 'completed') {
      if(socket_data['answered_by'] == 'human')
        caption = 'Sent Live';
      else if(socket_data['answered_by'] == 'machine')
        caption = 'Sent Voicemail';
    }
    else if(socket_data['call_status'] == 'failed') {
      if('error_msg' in socket_data)
        caption = socket_data['error_msg'];
      else
        caption = 'Failed';
    }
    else if(socket_data['call_status'] == 'busy' || socket_data['call_status'] == 'no-answer')
      caption += ' (' + socket_data['attempts'] + 'x)';

    formatCallStatus($cell, caption);
//    $cell.html(caption.toTitleCase()); 
  }
  if('speak' in socket_data) {
    var title = 'Msg: ' + socket_data['speak'];
    $row.find('[name="call_status"]').attr('title', title);
  }
}

// View: show_calls
// Display timer counting down until event_datetime
function updateCountdown() {
  $summary_lbl = $('#job-summary');
  var event_datetime = $('#scheduled_datetime').text();
  var scheduled = Date.parse(event_datetime);
  var today = new Date();
  var diff_ms = scheduled.getTime() - today.getTime();

  var diff_days = diff_ms / (1000 * 3600 * 24);
  var diff_hrs = ((diff_days + 1) % 1) * 24;
  var diff_min = ((diff_hrs + 1) % 1) * 60;
  var diff_sec = ((diff_min + 1) % 1) * 60;
  
  $('#job-summary').css({'color':'#009900'});
  
  $summary_lbl.text(
    Math.floor(diff_days) + ' Days ' + 
    Math.floor(diff_hrs) + ' Hours ' + 
    Math.floor(diff_min) + ' Min ' + 
    Math.floor(diff_sec) + ' Sec');
}

// View: show_jobs
function initShowJobs() {
  addBravoTooltip();
  console.log('script_root: ' + $SCRIPT_ROOT);

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
      var $tr = $(this).parent().parent();
      var job_uuid = $tr.attr('id');
      console.log('prompt to delete job_id: ' + job_uuid);
      var buttons = [
        { text: "No", 
          click: function() { $( this ).dialog( "close" ); }}, 
        { text: 'Yes', 
          click: function() {
            $(this).dialog('close');
            var request =  $.ajax({
              type: 'GET',
              url: $SCRIPT_ROOT + '/cancel/job/'+job_uuid
            });
            request.done(function(msg){
              if(msg == 'OK')
                $tr.remove();
            });
          }
        }
      ];
      showDialog($('#dialog'), msg, 'Confirm Action', buttons);
    });
  });

  $('body').css('display','block');
}

function initJobSummary() {
  var data = JSON.parse($('#content').text());
  $('#content').html('');
  $('#content').append(printJsonObj('totals', data['totals'], 0));
  $('#content').append('<br><br>');
  $('#content').append(printJsonObj('calls', data['calls'], 0));
  $('body').css('display','block');
}

function printJsonObj(parent_key, obj, indent_lvl) {
  var base_indent = '&nbsp;&nbsp;';
  var indent = '';
  var str = '';
  for(var i=0; i<indent_lvl; i++)
    indent += base_indent;

  if(obj instanceof Array) {
    str += indent + parent_key.toTitleCase() + ': <br>';
    for(var i=0; i<obj.length; i++) {
      //if(obj[i] instanceof Object)
        str += printJsonObj(i, obj[i], indent_lvl+1);
      str+='<br>';
    }
  }
  else if(obj instanceof Object) {
    for(var property in obj) {
      if(property == 'speak')
        continue;
      if(obj[property] instanceof Object)
        str += 
          indent + property.toTitleCase() + ': <br>' + 
          printJsonObj(property, obj[property], indent_lvl+1);
      else
        str += indent + property.toTitleCase() + ': ' + String(obj[property]).toTitleCase() + '<br>';
    }
  }
  return str;
}
