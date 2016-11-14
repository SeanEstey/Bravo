
//------------------------------------------------------------------------------
function new_event_init() {
  alertMsg('Schedule a new notification event', 'info', 7500);

  loadTooltip();

  $('#delivery_date').datepicker();
  $('#notific_date').datepicker();

  onSelectTemplate();

  $submit_btn = $('#submit_btn');

  $submit_btn.click(function(event){
      // This line needs to be here for Firefox browsers
      event.preventDefault(event);

      validateNewJobForm();


  });

  $('#radio').buttonset();
  
  // Init socket.io
  var socketio_url = 'http://' + document.domain + ':' + location.port;

  var socket = io.connect(socketio_url);

  socket.on('connected', function(){
    console.log('socket.io connected!');
  });

  socket.on('record_audio', function(data) {
    if(typeof data == 'string')
      data = JSON.parse(data);

    console.log('received record_audio socket: ' + JSON.stringify(data));

    if('audio_url' in data) {
      $('#record-status').text('Recording complete. You can listen to the audio below.');
      $('#audio-source').attr('src', data['audio_url']);
      $('#music').load();
      $('#audioplayer').show();
     // $('#audioplayer').fadeIn('slow');
      console.log('showing audio player');
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
      url: $URL_ROOT + 'reminders/voice/record/request',
      data: {'To':phone}
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

//------------------------------------------------------------------------------
function clickPercent(e) {
	/* Audio Player
	 * returns click as decimal (.77) of the total timelineWidth
	 */

  var timeline = document.getElementById('timeline'); // timeline
  var playhead = document.getElementById('playhead');
  var timelineWidth = timeline.offsetWidth - playhead.offsetWidth;
  return (e.pageX - timeline.offsetLeft) / timelineWidth;
}

//------------------------------------------------------------------------------
var onplayhead = false;
// mouseDown EventListener
function mouseDown() {
	/* Audio Player
	 * Boolean value so that mouse is moved on mouseUp only when the 
	 * playhead is released 
	 */

  var music = document.getElementById('music');
  onplayhead = true;
  window.addEventListener('mousemove', moveplayhead, true);
  music.removeEventListener('timeupdate', timeUpdate, false);
}

//------------------------------------------------------------------------------
function mouseUp(e) {
	/* Audio Player
	 * mouseUp EventListener. getting input from all mouse clicks
	 */

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


//------------------------------------------------------------------------------
function moveplayhead(e) {
	/* Audio Player
	 * mousemove EventListener. Moves playhead as user drags
	 */

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

//------------------------------------------------------------------------------
function timeUpdate() {
	/* Audio Player 
	 * Synchronizes playhead position with current point in audio 
	 */

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

//------------------------------------------------------------------------------
function play() {
	/* Audio Player */

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

//------------------------------------------------------------------------------
function onSelectTemplate() {
  var $select = $('#template-select');

  $select.change(function(){
    var $template = $select.find($('option:selected'));

    if($template.attr('id') == 'bpu') {
      $('[name="event_name"]').hide();
      $('[name="delivery_date"]').hide();
      $('#record-audio').hide();
      $('#record-text').hide();
      $('#schedule_fields').hide();
    }
    else if($template.attr('id') == 'green_goods') {
      $('[name="event_name"]').show();
      $('[name="delivery_date"]').show();
      $('#record-audio').hide();
      $('#record-text').hide();
      $('#schedule_fields').show();
    }
    else if($template.attr('id') == 'announcement') {
      $('[name="event_name"]').show();
      $('[name="delivery_date"]').hide();
      $('#record-audio').show();
      $('#record-text').hide();
      $('#schedule_fields').show();
    }
  });
}

//------------------------------------------------------------------------------
function validateNewJobForm() {
  var paramObj = {};

  $.each($('form').serializeArray(), function(_, kv) {
    paramObj[kv.name] = kv.value;
  }); 

  console.log(paramObj);

  // Validate form data
  var missing = [];
  var expired_date = false;
  var invalid_date = false;
  var scheduled_date = null;

  if(paramObj['template_name'] != 'bpu') {
      if(!paramObj['notific_time'])
        missing.push('Schedule Time');

      if(!paramObj['notific_date'])
        missing.push('Schedule Date');
      else {
        var now = new Date();
        var date_str = paramObj['notific_date'];

        if(paramObj['notific_time'])
          date_str += ', ' + paramObj['notific_time'];

        // Datejs for parsing strings like '12pm'
        scheduled_date = Date.parse(date_str);

        if(!scheduled_date)
          invalid_date = true;
        else if(scheduled_date.getTime() < now.getTime())
          expired_date = true;
      }
  }
  
  if(paramObj['template'] == 'announcement') {
    console.log('voice announcement');
    console.log('audio url='+paramObj['audio-url']);

    if(!$('#audio-source').attr('src'))
      missing.push('Voice Recording');
  }

  var msg = ''; 

  if(missing.length > 0) {
    msg = 'You forgot to enter: ';
    msg += '<b>' + missing.join(', ') + '</b><br><br>';
  }

  // $('#btn-default').addClass('btn-primary');

  if(missing.length > 0) {
      /*
      $('.modal-title').text('Missing Fields');
      $('.modal-body').html(msg);
      $('#btn-primary').text('Ok');
      $('#btn-primary').click(function() {
        $('#mymodal').modal('hide');
      });
      $('#btn-primary').hide();
      $('#mymodal').modal('show');
      */
  }
  else if(expired_date) {
      /*
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
      */
  }
  else if(invalid_date) {
      /*
      $('.modal-title').text('Invalid Date/Time');
      $('.modal-body').text('Could not understand the date and time provided. Please correct.');
      $('#btn-primary').hide();
      $('#mymodal').modal('show');
      */
  }
  else {
      // event.preventDefault();

      var form_data = new FormData($('#myform')[0]);

      $('#new_event_modal').modal('hide');

      $('.loader-div').slideToggle(function() {
          $('.btn.loader').fadeTo('slow', 1);
      });

      $.ajax({
        type: 'POST',
        url: $URL_ROOT + 'notify/new',
        data: form_data,
        contentType: false,
        processData: false,
        dataType: 'json'
      })
      .done(function(response) {
          if(response['status'] != 'success') {
              alertMsg('Response: ' + response['description'], 'danger');

              $('.btn.loader').fadeTo('slow', 0, function() {
                  $('.loader-div').slideToggle();
              });

              return;
          }

          console.log(response);

          addEvent(
            response['event'],
            response['view_url'],
            response['cancel_url'],
            response['description']);

          $('.btn.loader').fadeTo('slow', 0, function() {
              $('.loader-div').slideToggle();
          });
      });

  }
}
