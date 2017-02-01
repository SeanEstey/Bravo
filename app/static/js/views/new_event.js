
//------------------------------------------------------------------------------
function new_event_init() {
    alertMsg(
      'Schedule a new notification event', 
      'info', 7500, 'new_event_alert'
    );

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
        alertMsg('Attempting call...', 'info', 7500, 'new_event_alert');

        $.ajax({
          type: 'POST',
          url: $URL_ROOT + 'api/notify/events/record',
          data: {'To':$('#phone-num').val()}
        })
        .done(function(response) {
            if(response['status'] == 'queued')
                alertMsg('Dialing...', 'info', 7500, 'new_event_alert');
            else if(response['status'] == 'failed')
                alertMsg(response['description'], 'danger', 30000, 'new_event_alert');
        });
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
        console.log('record_audio: ' + JSON.stringify(data));

        if(data['status'] == 'answered') {
            alertMsg(
              'Call answered. Listen to the instructions to record your announcement',
              'info', 7500, 'new_event_alert'
            );
        }
        else if(data['status'] == 'recorded') {
            alertMsg(
              'Recording complete. You can listen to the audio below',
              'success', 15000, 'new_event_alert'
            );

            $('#audio_url').val(data['audio_url']);
            $('#audio_source').attr('src', data['audio_url']);

            try {
               $('#music')[0].load();
            }
            catch(err) {
              console.log(err);
            }

            $('.audioplayer').show();
            $('.audioplayer').fadeIn('slow');
        }
        else if(data['status'] == 'failed') {
            alertMsg(data['description'], 'danger', 30000, 'new_event_alert');
        }
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
    var form = {};

    $.each($('form').serializeArray(), function(_, kv) {
      form[kv.name] = kv.value;
    }); 

    console.log(form);

    var missing = [];
    var expired_date = false;

    switch(form['template_name']) {
        case 'bpu':
            var required = ['query_name', 'query_category'];

            for(var idx in required) {
                if(!form[required[idx]])
                    missing.push(required[idx]);
            }
            break;
        case 'green_goods':
            var required = ['query_name', 'query_category', 'notific_time',
            'notific_date', 'event_date'];

            for(var idx in required) {
                if(!form[required[idx]])
                    missing.push(required[idx]);
            }
            break;
        case 'recorded_announcement':
            var required = ['query_name', 'query_category', 'notific_time',
            'notific_date', 'audio_url'];
            
            for(var idx in required) {
                if(!form[required[idx]])
                    missing.push(required[idx]);
            }
            break;
        default:
            break;
    }

    if(missing.length > 0) {
        msg = 'You forgot to enter: ';
        msg += '<strong>' + missing.join(', ') + '</strong>';
        alertMsg(msg, 'danger', 30000, 'new_event_alert');
        return;
    }

    if(form['template_name'] != 'bpu') {
        var schedule_date = Date.parse(
          form['notific_date'] + ', ' + form['notific_time']
        );

        if(!schedule_date) {
            alertMsg('Invalid scheduled date/time', 'danger', 30000, 'new_event_alert');
            return;
        }
        else if(schedule_date.getTime() < new Date().getTime()) {
            alertMsg('Invalid scheduled date/time', 'danger', 30000, 'new_event_alert');
            expired_date = true;
        }
    }

    var msg = ''; 

    if(expired_date) {
				console.log('showing expired date warning modal');

        msg = 'The scheduled date is before the present:<br><br>' + 
        '<b>' + schedule_date.toString('dddd, MMMM d, yyyy @ hh:mm tt') + 
        '</b><br><br>' +
        'Do you want to start this job now?';

        $('#mymodal .modal-title').text('Confirm');
        $('#mymodal .modal-body').html(msg);
        $('#mymodal .btn-primary').text('Start Job');
        $('#mymodal .btn-secondary').text('Cancel');

        $('#mymodal .btn-primary').click(function() {
						$('#mymodal').modal('hide');
						$('#new_event_modal').modal('hide');
						submit(new FormData($('#myform')[0]));
        });

				$('#mymodal .btn-secondary').click(function() {
						$('#new_event_modal').modal('show');
						$('#mymodal').modal('hide');
						$(this).click(function() {});
				});

				$('#new_event_modal').modal('hide');
        $('#mymodal').modal('show');
    }
		else {
				$('#new_event_modal').modal('hide');

				$('.loader-div').slideToggle(function() {
						$('.btn.loader').fadeTo('slow', 1);
				});

				submit(new FormData($('#myform')[0]));
		}
}

//------------------------------------------------------------------------------
function submit(form_data) {
		$.ajax({
			type: 'POST',
			url: $URL_ROOT + '/api/notify/events/create',
			data: form_data,
			contentType: false,
			processData: false,
			dataType: 'json'
		})
		.done(function(response) {
				if(response['status'] != 'success') {
						console.log(response);

						alertMsg(
							'Response: ' + response['data']['description'], 
							'danger', 30000)

						$('.btn.loader').fadeTo('slow', 0, function() {
								$('.loader-div').slideToggle();
						});

						return;
				}

				console.log(response);

				addEvent(
					response['data']['event'],
					response['data']['view_url'],
					response['data']['cancel_url'],
					response['data']['description']);

				$('.btn.loader').fadeTo('slow', 0, function() {
						$('.loader-div').slideToggle();
				});
		});
}
