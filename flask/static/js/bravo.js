// GLOBALS
this.colors = {
  'SUCCESS_STATUS': '#5CB85C',
  'FAILED_STATUS': '#D9534F',
  'DEFAULT_STATUS': 'black',
  'IN_PROGRESS_STATUS': '#337AB7'
};
	
this.unicode = {
  'UP_ARROW': '&#8593;',
  'DOWN_ARROW': '&#8595;',
  'SPACE': '&#32;'
};

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
  /*
  $("input[type=submit], button")
    .button()
    .click(function( event ) {
      event.preventDefault();
    });
    */
}

function getServerStatus(variable) {
  var request =  $.ajax({
      type: 'GET',
      url: $URL_ROOT + 'get/' + variable
    });

  request.done(function(msg){
    console.log(msg);
  });
}

function displayServerStatus(route, label, $element) {
  var request =  $.ajax({
      type: 'GET',
      url: $URL_ROOT + route
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

// login view
function initLoginView() {
  console.log('Root url: ' + $URL_ROOT);
  $('#app_menu').hide();

  $('#submit_btn').click(function(event){
    // This line needs to be here for Firefox browsers
    event.preventDefault(event);
    
    var form_data = new FormData($('#myform')[0]);
    var request = $.ajax({
      type: 'POST',
      url: $URL_ROOT + 'login',
      data: form_data,
      contentType: false,
      processData: false,
      dataType: 'json'
    })
    
    request.done(function(response){
      console.log(response);
      if(typeof response == 'string')
        response = JSON.parse(response);
      if(response['status'] == 'success') {
        console.log('login success');
        location.href = $URL_ROOT;
      }
      else if(response['status'] == 'error') {
        $('.modal-title').text(response['title']);
        $('.modal-body').html(response['msg']);
        $('#btn-primary').hide();
        $('#mymodal').modal('show');
      }
    });
    
    request.fail(function(xhr, textStatus, errorThrown) {
      console.log(xhr);
      console.log(textStatus);
      console.log(errorThrown);
      $('.modal-title').text('Error');
      $('.modal-body').html(xhr.responseText);
      $('.btn-primary').hide();
      $('#mymodal').modal('show');
    });
  });

  $('body').css('display','block');
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
  $submit_btn.click(function(event){
    // This line needs to be here for Firefox browsers
    event.preventDefault(event);
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
      var rounded = Math.ceil(duration);
      $('#duration').text(String(rounded)+' sec'); 
    }, false);

    event.preventDefault();
    var phone = $('#phone-num').val();
    var request =  $.ajax({
      type: 'POST',
      url: $URL_ROOT + 'recordaudio',
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
    url: $URL_ROOT + 'reminders/get_job_template/' + $template.attr('value')
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

  $('#btn-default').addClass('btn-primary');

  if(missing.length > 0 || wrong_filetype) {
    $('.modal-title').text('Missing Fields');
    $('.modal-body').html(msg);
    $('#btn-primary').text('Ok');
    $('#btn-primary').click(function() {
      $('#mymodal').modal('hide');
    });
    $('#btn-primary').hide();
    $('#mymodal').modal('show');
  }
  else if(expired_date) {
    msg = 'The scheduled date is before the present:<br><br>' + 
    '<b>' + scheduled_date.toString('dddd, MMMM d, yyyy @ hh:mm tt') + 
    '</b><br><br>' +
    'Do you want to start this job now?';

    $('.modal-title').text('Confirm');
    $('.modal-body').html(msg);
    $('#btn-primary').text('Start Job');
    $('#btn-primary').text('No');
    $('#btn-primary').click(function() {
  //     $('form').submit();
    });
    $('#mymodal').modal('show');
  }
  else if(invalid_date) {
    $('.modal-title').text('Invalid Date/Time');
    $('.modal-body').text('Could not understand the date and time provided. Please correct.');
    $('#btn-primary').hide();
    $('#mymodal').modal('show');
  }
  else {
    // event.preventDefault();

    var form_data = new FormData($('#myform')[0]);

    var request = $.ajax({
      type: 'POST',
      url: $URL_ROOT + '/reminders/submit_job',
      data: form_data,
      contentType: false,
      processData: false,
      dataType: 'json'
    })
    
    request.done(function(response){
      console.log(response);

      if(typeof response == 'string')
        response = JSON.parse(response);

      if(response['status'] == 'success') {
        var end = location.href.indexOf('new');

        //location.href = location.href.substring(0,end) + '?msg='+response['msg'];
        
        location.href = $URL_ROOT;
      }
      else if(response['status'] == 'error') {
        $('.modal-title').text(response['title']);
        $('.modal-body').html(response['msg']);
        $('#btn-primary').hide();
        $('#mymodal').modal('show');
      }
    });
    
    request.fail(function(xhr, textStatus, errorThrown) {
      console.log(xhr);
      console.log(textStatus);
      console.log(errorThrown);
      $('.modal-title').text('Error');
      $('.modal-body').html(xhr.responseText);
      $('.btn-primary').hide();
      $('#mymodal').modal('show');
    });
  }
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
        $status_td.css({'color':'green'}); // FIXME: Breaks Bootstrap style
    else if(data['status'] == "in-progress")
        $status_td.css({'color':'red'}); // FIXME: Breaks Bootstrap style
      
    $status_td.text(data['status'].toTitleCase());
    //$('.delete-btn').hide();
  });

  if(location.href.indexOf('?msg=') > -1) {
      var uri = decodeURIComponent(location.href);
      var ind = uri.indexOf('?msg=');
      var msg = uri.substring(ind+5, uri.length);
      $('#status-banner').text(msg);
  }

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
      var $tr = $(this).parent().parent();
      var job_uuid = $tr.attr('id');

      console.log('prompt to delete job_id: ' + job_uuid);

      $('.modal-title').text('Confirm');
      $('.modal-body').text('Really delete this job?');
      $('#btn-secondary').text('No');
      $('#btn-primary').text('Yes');

      $('#btn-primary').click(function() {
          var request =  $.ajax({
              type: 'GET',
              url: $URL_ROOT + 'reminders/'+job_uuid+'/cancel'
          });

          request.done(function(msg){
              if(msg == 'OK')
                $tr.remove();
          });
          $('#mymodal').modal('hide'); 
      });

      $('#mymodal').modal('show');
    });
  });

  var num_page_records = $('tbody').children().length;
  var n = 1;
  var n_ind = location.href.indexOf('n=');

  if(n_ind > -1) {
    if(location.href.indexOf('&') > -1)
      n = location.href.substring(n_ind+2, location.href.indexOf('&'));
    else
      n = location.href.substring(n_ind+2, location.href.length);

    n = parseInt(n, 10);
  }

  console.log(n);
  console.log(num_page_records);

  $('#newer-page').click(function() {
    if(n > 1) {
      var prev_n = n - num_page_records;
      if(prev_n < 1)
        prev_n = 1;
      location.href = $URL_ROOT + '?n='+prev_n;
    }
  });
  
  $('#older-page').click(function() {
    var next_n = num_page_records + 1;

    if(n)
      next_n += n;

    location.href = $URL_ROOT + '?n='+next_n;
  });

  $('body').css('display','block');
}

function initJobSummary() {
  var data = JSON.parse($('#content').text());
  $('#content').html('');
  $('#content').append(objToHtml(data, 0, ['speak']));
  $('body').css('display','block');
}

function initLog() {
  $('body').css('display','block');
}

function initAdmin() {
  $('body').css('display','block');
  displayServerStatus('/get/celery_status', '', $('#celery-status'));
  displayServerStatus('/get/version', '', $('#version'));
  displayServerStatus('/get/monthly_usage', '', $('#monthly-usage'));
  displayServerStatus('/get/annual_usage', '', $('#annual-usage'));
}

function objToHtml(obj, indents, ignores) {
  /*Converts a JS Object to indented, color-coded HTML (no braces/brackets)
  Properties are sorted alphabetically
  */

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
      str += '<label style="color:green;">' + String(obj[key]) + '</label><br>';
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
