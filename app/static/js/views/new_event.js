
//------------------------------------------------------------------------------
function new_event_init() {
    alertMsg('Schedule a new notification event', 'info', 7500);

    newEventBtnHandlers();
    newEventSocketIOHandlers();
    loadTooltip();

    $('#event_date').datepicker();
    $('#notific_date').datepicker();

    onSelectTemplate();

    $('#radio').buttonset();

    $('body').css('display','block');
}


//------------------------------------------------------------------------------
function newEventBtnHandlers() {

    $('#submit_btn').click(function(event){
        event.preventDefault(event);
        validateNewJobForm();
    });

    $('#call_btn').click(function() {
        event.preventDefault();

        $.ajax({
          type: 'POST',
          url: $URL_ROOT + 'notify/record',
          data: {'To':$('#phone-num').val()}
        })
        .done(function(response) {
            if(response['call_status'] == 'failed') {
              $('#record-status').text(response['error_msg'].toTitleCase());
            }
            else if(response['call_status'] == 'queued') {
              $('#record-status').text('Calling...');
            }
            $('#record-status').clearQueue();
            $('#record-status').fadeIn('slow');
            $('#record-status').delay(10000);
        });
          
        $('#record-status').text('Attempting Call...');
        $('#record-status').clearQueue();
    });
}

//------------------------------------------------------------------------------
function newEventSocketIOHandlers() {
    var socketio_url = 'http://' + document.domain + ':' + location.port;
    var socket = io.connect(socketio_url);

    socket.on('connected', function(){
        console.log('socket.io connected!');
    });

    socket.on('record_audio', function(data) {
        console.log('received record_audio socket: ' + JSON.stringify(data));

        $('#record-status').text('Recording complete. You can listen to the audio below.');

        $('#audio_url').val(data['audio_url']);

        $('#audio-source').attr('src', data['audio_url']);

        try {
           $('#music')[0].load();
        }
        catch(err) {
          console.log(err);
        }

        $('.audioplayer').show();

        $('.audioplayer').fadeIn('slow');

        console.log('showing audio player');
    });
}

//------------------------------------------------------------------------------
function onSelectTemplate() {
  var $select = $('#template-select');

  $select.change(function(){
    var $template = $select.find($('option:selected'));

    if($template.attr('id') == 'bpu') {
      $('[name="event_name"]').hide();
      $('[name="event_date"]').hide();
      $('#record-audio').hide();
      $('#record-text').hide();
      $('#schedule_fields').hide();
    }
    else if($template.attr('id') == 'green_goods') {
      $('[name="event_name"]').show();
      $('[name="event_date"]').show();
      $('#record-audio').hide();
      $('#record-text').hide();
      $('#schedule_fields').show();
    }
    else if($template.attr('id') == 'recorded_announcement') {
      $('[name="event_name"]').show();
      $('[name="event_date"]').hide();
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
    console.log('audio url='+paramObj['audio_url']);

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
