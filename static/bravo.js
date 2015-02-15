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

// Replace underscores with spaces, capitalizes words
String.prototype.toTitleCase = function(n) {
   var s = this;
   if (1 !== n) 
     s = s.toLowerCase();
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
    $element.html(msg.toTitleCase());
    $element.hide();
    $element.fadeIn('slow');
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

// new_job view
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
  $('#radio').buttonset();
  
  // Init socket.io
  var socketio_url = 'http://' + document.domain + ':' + location.port;
  console.log('attempting socket.io connection to ' + socketio_url + '...');
  var socket = io.connect(socketio_url);
  socket.on('connect', function(){
    socket.emit('connected');
    console.log('connected!');
  });

  socket.on('record_audio', function(data) {
    if(typeof data == 'string')
      data = JSON.parse(data);

    console.log('received record_audio socket: ' + JSON.stringify(data));

    if('audio_url' in data) {
      $('#record-status').text('Recording complete. You can listen to the audio below.');
      $('#audio-source').attr('src', data['audio_url']);
      $('#music').load();
      $('#audioplayer').fadeIn('3000');
      // Add url to form element for submission
      $('#input-audio-url').val(data['audio_url']);
      return;
    }
    if('msg' in data) {
      $('#record-status').text(data['msg']);
      return;
    }
  });
  
  $('#call-btn').click(function() {
    // AUDIO PLAYER
    var music = document.getElementById('music');
    var duration;
    var pButton = document.getElementById('pButton');
    var playhead = document.getElementById('playhead');
    var timeline = document.getElementById('timeline');
    var timelineWidth = timeline.offsetWidth - playhead.offsetWidth;
    
    music.addEventListener("timeupdate", timeUpdate, false);
    timeline.addEventListener("click", function (event) {
      moveplayhead(event);
      music.currentTime = duration * clickPercent(event);
    }, false);

    // Makes playhead draggable 
    playhead.addEventListener('mousedown', mouseDown, false);
    window.addEventListener('mouseup', mouseUp, false);
    
    // Gets audio file duration
    music.addEventListener("canplaythrough", function () {
      var music = document.getElementById('music');
      duration = music.duration;  
    }, false);

    var phone = $('#phone-num').val();
    var request =  $.ajax({
      type: 'POST',
      url: $SCRIPT_ROOT + '/recordaudio',
      data: {'to':phone}
    });
    
    $('#record-status').text('Attempting Call...');
    $('#record-status').clearQueue();
    
    request.done(function(msg) {
      if(typeof msg == 'string') 
        msg = JSON.parse(msg);

      if(msg['call_status'] == 'failed') {
        $('#record-status').text(msg['error_msg'].toTitleCase());
      }
      else if(msg['call_status'] == 'queued') {
        $('#record-status').text('Calling...');
      }
      $('#record-status').clearQueue();
      $('#record-status').fadeIn('slow');
      $('#record-status').delay(10000);
    });
  });
  
  $('body').css('display','block');
}

// Audio Player
// returns click as decimal (.77) of the total timelineWidth
function clickPercent(e) {
  var timeline = document.getElementById('timeline'); // timeline
  var playhead = document.getElementById('playhead');
  var timelineWidth = timeline.offsetWidth - playhead.offsetWidth;
  return (e.pageX - timeline.offsetLeft) / timelineWidth;
}

// Audio Player
// Boolean value so that mouse is moved on mouseUp only when the playhead is released 
var onplayhead = false;
// mouseDown EventListener
function mouseDown() {
  var music = document.getElementById('music');
  onplayhead = true;
  window.addEventListener('mousemove', moveplayhead, true);
  music.removeEventListener('timeupdate', timeUpdate, false);
}

// Audio Player
// mouseUp EventListener. getting input from all mouse clicks
function mouseUp(e) {
  var music = document.getElementById('music');
  if (onplayhead == true) {
    moveplayhead(e);
    window.removeEventListener('mousemove', moveplayhead, true);
    // change current time
    music.currentTime = music.duration * clickPercent(e);
    music.addEventListener('timeupdate', timeUpdate, false);
  }
  onplayhead = false;
}

// Audio Player
// mousemove EventListener. Moves playhead as user drags
function moveplayhead(e) {
  var timeline = document.getElementById('timeline');
  var playhead = document.getElementById('playhead');
  var timelineWidth = timeline.offsetWidth - playhead.offsetWidth;
  var newMargLeft = e.pageX - timeline.offsetLeft;

  if (newMargLeft >= 0 && newMargLeft <= timelineWidth) {
    playhead.style.marginLeft = newMargLeft + "px";
  }
  if (newMargLeft < 0) {
    playhead.style.marginLeft = "0px";
  }
  if (newMargLeft > timelineWidth) {
    playhead.style.marginLeft = timelineWidth + "px";
  }
}

// Audio Player 
// Synchronizes playhead position with current point in audio 
function timeUpdate() {
  var music = document.getElementById('music');
  var pButton = document.getElementById('pButton');
  var timeline = document.getElementById('timeline');
  var playhead = document.getElementById('playhead');
  var timelineWidth = timeline.offsetWidth - playhead.offsetWidth;
  var playPercent = timelineWidth * (music.currentTime / music.duration);
  
  playhead.style.marginLeft = playPercent + "px";
  
  if (music.currentTime == music.duration) {
    pButton.className = "";
    pButton.className = "play";
  }
}

// Audio Player
function play() {
  var music = document.getElementById('music');
  var pButton = document.getElementById('pButton');
  
  if (music.paused) {
    music.play();
    // remove play, add pause
    pButton.className = "";
    pButton.className = "pause";
  } 
  else {
    music.pause();
    // remove pause, add play
    pButton.className = "";
    pButton.className = "play";
  }
}

// new_job view
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

// new_job view
function onSelectTemplate() {
  var $select = $('#template-select');
  $select.change(function(){
    var $template = $select.find($('option:selected'));
    updateFilePickerTooltip();
    $('#audioplayer').hide();
    if($template.val() == 'etw_reminder') {
      $('#record-audio').hide();
      $('#record-text').hide();
    }
    else if($template.val() == 'gg_delivery') {
      $('#record-audio').hide();
      $('#record-text').hide();
    }
    else if($template.val() == 'announce_voice') {
      $('#record-audio').show();
      $('#record-text').hide();
    }
    else if($template.val() == 'announce_text') {
      $('#record-text').show();
      $('#record-audio').hide();
    }
  });
}

// new_job view
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
  if(paramObj['template'] == 'announce_voice') {
    console.log('voice announcement');
    console.log('audio url='+paramObj['audio-url']);
    if(!$('#audio-source').attr('src'))
      missing.push('Voice Recording');
  }
  else if(paramObj['template'] == 'announce_text') {
    if(!paramObj['message'])
      missing.push('Text Announcement');
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
  else
    $('.delete-btn').hide();

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
  socket.on('connect', function(){
    socket.emit('connected');
    console.log('socket.io connected!');
  });
  socket.on('update_call', function(data) {
    receiveCallUpdate(data);
  });
  socket.on('update_job', function(data) {
    console.log('received update: ' + JSON.stringify(data));
    if(data['status'] == 'completed') {
      console.log('job complete!');
      $('#job-status').text('Completed');
      showJobSummary();
      $('.delete-btn').hide();
    }
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
  if(text.indexOf('Sent') > -1)
    $cell.css({'color':'#009900'});
  else if(text.indexOf('Failed') > -1)
    $cell.css({'color': '#C00000'});
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

// View: show_calls
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
        caption = 'Failed (' + socket_data['error_msg'] + ')';
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
  var scheduled_date = Date.parse($('#scheduled_datetime').text());
  var today = new Date();
  var diff_ms = scheduled_date.getTime() - today.getTime();

  if(diff_ms < 0) {
    $summary_lbl.text('0 Days 0 Hours 0 Min 0 Sec');
    return;
  }

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
  
  // Init socket.io
  var socketio_url = 'http://' + document.domain + ':' + location.port;
  console.log('attempting socket.io connection to ' + socketio_url + '...');
  var socket = io.connect(socketio_url);
  socket.on('connect', function(){
    socket.emit('connected');
    console.log('socket.io connected!');
  });
  socket.on('update_job', function(data) {
    // data format: {'id': id, 'status': status}
    if(typeof data == 'string')
      data = JSON.parse(data);
    console.log('received update: ' + JSON.stringify(data));
    $job_row = $('#'+data['id']);
    if(!$job_row)
      return console.log('Could not find row with id=' + data['id']);
   
    var job_name = $job_row.find('[name="job-name"]').text(); 
    var msg = 'Job \''+job_name+'\' ' + data['status'];
    $('#status-banner').text(msg);
    $('#status-banner').clearQueue();
    $('#status-banner').fadeIn('slow');
    $('#status-banner').delay(10000);
    $('#status-banner').fadeOut(3000);

    $status_td = $job_row.find('[name="job-status"]');
    if (data['status'] == "completed")
      $status_td.css({'color':'green'});
    else if(data['status'] == "in-progress")
      $status_td.css({'color':'red'});
      
    $status_td.text(data['status'].toTitleCase());   
    //$('.delete-btn').hide();
  });

  if($('#status-banner').text()) {
    $('#status-banner').fadeIn('slow');
    $('#status-banner').delay(10000);
    $('#status-banner').fadeOut(3000);
  }

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
  $('#content').append(objToHtml(data, 0, ['speak']));
  $('body').css('display','block');
}

// Converts a JS Object to indented, color-coded HTML (no braces/brackets)
// Properties are sorted alphabetically
function objToHtml(obj, indents, ignores) {
  var indent = '';
  var str = '';
  var toClass = {}.toString;
  for(var i=0; i<indents; i++)
    indent += '&nbsp;&nbsp';

  var sorted_keys = Object.keys(obj).sort();
  var key;

  for(var index in sorted_keys) {
    key = sorted_keys[index];
    if(ignores.indexOf(key) > -1)
      continue;
    // MongoDB Timestamp
    if(key.indexOf('$date') > -1) {
      str += indent + 'Date: ';
      var date_str = new Date(obj[key]);
      str += '<label style="color:green;">' + date_str + '</label><br>'; 
    }
    // Primitive
    else if(typeof obj[key] != 'object') {
      str += indent + key.toTitleCase() + ': ';
      str += '<label style="color:green;">' + String(obj[key]).toTitleCase() + '</label><br>';
    }
    // Date
    else if(toClass.call(obj[key]) == '[object Date]')
      str += indent + key.toTitleCase() + ': ' + obj[key].toString() + '<br>';
    // Array
    else if(toClass.call(obj[key]) == '[object Array]') {
      str += indent + key.toTitleCase() + ': <br>';
      var element_str;
      for(var i=0; i<obj[key].length; i++) {
        element_str = objToHtml(obj[key][i], indents+1, ignores);
        str += indent + element_str + '<br>';
      }
    }
    // Generic Object
    else if(toClass.call(obj[key]) == '[object Object]') {
      var obj_str = objToHtml(obj[key], indents+1, ignores);
      str += indent + key.toTitleCase() + '<br>' + obj_str;
    }
  }
  return str;
}
