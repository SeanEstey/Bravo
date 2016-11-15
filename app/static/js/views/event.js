
//------------------------------------------------------------------------------
function init() {
    loadTooltip();
    enableEditableFields();
		enableColumnSorting();
		formatColumns();
    buildAdminPanel();
    addDeleteBtnHandlers();
    addSocketIOHandlers();
		showAdminServerStatus();

		$('[data-toggle="tooltip"]').tooltip();
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    var socket = io.connect(socketio_url);

    socket.on('connect', function(){
        socket.emit('connected');
        console.log('socket.io connected!');
    });

    socket.on('notific_status', function(data) {
        console.log('notific %s [%s]', data['status'], data['notific_id']);

				$td = $('td#'+data['notific_id']);

        $td.text(data['status'].toTitleCase());
				
				if('description' in data)
						$td.attr('title', 'Desc: ' + data['description'] + '\n');

				if('answered_by' in data)
						$td.attr('title', $td.attr('title') + ' Answered By: ' + data['answered_by']);

        applyStatusColor($('td#'+data['notific_id']));
    });

		socket.on('trigger_status', function(data) {
				console.log('trigger %s [%s]', data['status'], data['trig_id']);
				
				if(data['status'] == 'in-progress') {
            alertMsg('Sending notifications...', 'info');

						var columns = $("#notific-table").find("tr:first th").length;

						// Hide 'delete' notific column
						$('#notific-table').find('td:nth-child('+String(columns)+')').hide();
						$('#notific-table').find('th:nth-child('+String(columns)+')').hide();

            $('#stop_btn').prop('disabled', false);
				}
				else if(data['status'] == 'fired') {
            $('#stop_btn').prop('disabled', true);

						alertMsg(data['sent'] + ' notifications sent. ' + 
											data['fails'] + ' failed. ' + data['errors'] + ' errors.',
											'success');
				}
		});

    socket.on('update_event', function(data) {
        if(typeof data == 'string')
            data = JSON.parse(data);

        console.log('received update: ' + JSON.stringify(data));

        if(data['status'] == 'in-progress') {
            console.log('in progress!');
            $('#event-status').text('In Progress');
            $('.cancel-call-col').each(function() {
                $(this).hide();
            });
        }
        else if(data['status'] == 'completed') {
            $('#event-header').removeClass('label-primary');
            $('#event-header').addClass('label-success');
            $('#event-status').text('Completed');
            $('#event-summary').text('');

            console.log('event complete!');
        }
          updateJobStatus();
    });
}

//------------------------------------------------------------------------------
function addDeleteBtnHandlers() {
      var args =  window.location.pathname.split('/');
      var evnt_id = args.slice(-1)[0];

      $('.delete-btn').each(function(){ 
					$(this).attr('data-original-title', 'Remove this notification');

          $(this).click(function() {
              var acct_id = $(this).attr('id');
              var $tr = $(this).parent().parent();

              $.ajax({
                type: 'POST',
                context: this,
		            url: $URL_ROOT + 'notify/' + evnt_id + '/' + acct_id + '/remove'
              })
              .done(function(response) {
                  console.log(response);
                  if(response['status'] == 'success'){ 
                      $(this).parent().parent().remove();
                      console.log('acct %s removed', $(this).attr('id'));
                      alertMsg('Notification removed', 'success');
                  }
                  else
                    alertMsg('Error removing notific', 'danger');
              });
          });
      });

    /*
    else if($('#event-status').text() == 'In Progress') {
        $('.cancel-call-col').each(function() {
          $(this).hide();
        });
    }
    else if($('#event-status').text() == 'Completed') {
        $('#event-header').removeClass('label-primary');
        $('#event-header').addClass('label-success');
        $('#event-status').text('Completed');
        $('#event-summary').text('');
        $('.delete-btn').hide();
        $('.cancel-call-col').each(function() {
            $(this).hide();
        });

        console.log('event complete!');
    }
    */
}

//------------------------------------------------------------------------------
function buildAdminPanel() {
		/* Each Trigger <button> stores 'trigId' and 'status' key/value pairs in
     * $(this).data() 
     */
   
			//	$('.admin-panel-div').accordion({header:'.admin-outer', collapsible:true});
/*
		$('.admin-outer').click(function() {
				console.log('slide');
				var height = $('.admin-panel-div').height();

		});*/

		
    // Add admin_mode pane buttons

    // Add btns to fire each event trigger. trig_ids are stored in data-container 
    // "Status" columns i.e. "Voice SMS Status"
    $('th[id] a:contains("Status")').parent().each(function() {
        console.log('adding fire btn for trig_id ' + $(this).attr('id'));

        var col_caption = $(this).children().text();

        if(col_caption.search("Email") > -1) {
          var btn_caption = 'Send Emails Now';
          var btn_id = 'fire-email-btn';
        }
        else if(col_caption.search("Voice") > -1) {
          var btn_caption = 'Send Voice/SMS Now';
          var btn_id = 'fire-voice-sms-btn';
        }

        btn = addAdminPanelBtn(
          'admin_pane',
          btn_id,
          btn_caption,
          'btn-outline-primary', {
            'trigId':$(this).attr('id')
          }
        );

        btn.click(function() {
            $.ajax({
              context: this,
              type: 'POST',
              url: $URL_ROOT + 'notify/' + $(this).data('trigId') + '/fire'
            })
            .done(function(response) {
                  console.log('request status: %s', response['status']);

                  if(response['status'] != 'OK') {
                      alertMsg('Request to send notifications denied.',
                      'danger');
                      return;
                  }

                  $(this).prop('disabled', true);
            });
        });

				// Get trigger status from server
				$.ajax({
					type: 'POST',
					url: $URL_ROOT + 'notify/' + btn.data('trigId') + '/get_status'})
				.done(function(response) {
						$.each( $(':data(trigId)'), function() {
								if($(this).data('trigId') == response['trig_id']) {
									$(this).data('status', response['status']);

									if(response['status'] != 'pending')
                    $(this).prop('disabled', true);
								}
						});
				}); 
    });

    stop_btn = addAdminPanelBtn(
      'admin_pane',
      'stop_btn',
      'Stop All',
      'btn-outline-danger ');

    stop_btn.prop('disabled', true);

		$.each( $(':data(status)'), function() {
				if($(this).data('status') == 'in-progress')
          $('#stop_btn').prop('disabled', false);
		});

    // Make server request to kill any active triggers
    stop_btn.click(function() {
        $.each(($(':data(trigId)')), function(){
            if($(this).data('status') != 'in-progress'){
                console.log('no active trigger to kill');
                return;
            }

            console.log('requesting to kill trigger %s', $(this).data('trigId'));

            $.ajax({
                type: 'post',
                url: $URL_ROOT + 'notify/kill_trigger',
                data: {'trig_id': $(this).data('trigId')}})
            .done(function(response) {
                console.log('response: ' + JSON.stringify(response));
                showBannerMsg(JSON.stringify(response));
                
                // TODO: have server send 'trigger_status' socket.io event on
                // success, update button enabled/disabled states
            });
        });

    });
    
    // Add dev_mode admin pane buttons

    var args =  window.location.pathname.split('/');
    var evnt_id = args.slice(-1)[0];

    reset_btn = addAdminPanelBtn(
      'dev_pane',
      'reset_btn',
      'Reset All',
      'btn-outline-primary');

    reset_btn.click(function() {
      $.ajax({
				type: 'GET',
				url: $URL_ROOT + 'notify/' + evnt_id + '/reset'
			})
			.done(function(response, textStatus, jqXHR) {
				window.location.reload();
			});
    });

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Debug Mode',
      'btn-outline-primary');

		// Add debug buttons that print notific['tracking'] data to console
    show_debug_info_btn.click(function() {
				$(this).prop('disabled', 'true');

				$('#notific-table th:last').after('<th>DEBUG</th>');

				$('tr[id]').each(function() {
						var $debug_btn = 
							'<button name="debug-btn" ' +
											'class="btn btn-outline-warning">Print Debug</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);

								var data = $(this).parent().parent().attr('data-tracking');

								// Try to convert unicode dict str to JSON object
								data = data.replace(/u\'/g, '\'').replace(/\'/g, '\"').replace(/None|False|True/g, '\"\"');

								try {
										console.log(JSON.stringify(JSON.parse(data), null, 4));
								}
								catch(e) {
										console.log('couldnt convert to JSON obj.');
										console.log(data);
								}
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Debug</b> buttons prints notification info to console.', 'info');
    });
}

//------------------------------------------------------------------------------
function setupTwilioClient() {
		// Set up with TOKEN, a string generated server-side

    $('#play-sample-btn').click(function() {
			$.ajax({
				type: 'GET',
				url: $URL_ROOT + 'notify/get/token'
			}).done(function(token) {
				console.log('token received: ' + token['token']);

				Twilio.Device.setup(token['token']);

				var connection = Twilio.Device.connect();
			//	{
				 // agent: "Smith",
				//	phone_number: "4158675309"
			//	});

			});
    });

		Twilio.Device.ready(function() {
				// Could be called multiple times if network drops and comes back.
				// When the TOKEN allows incoming connections, this is called when
				// the incoming channel is open.
				console.log('Twilio device ready');
		});

		Twilio.Device.offline(function() {
				// Called on network connection lost.
		});

		Twilio.Device.incoming(function(conn) {
				console.log(conn.parameters.From); // who is calling
				conn.status // => "pending"
				conn.accept();
				conn.status // => "connecting"
		});

		Twilio.Device.cancel(function(conn) {
				console.log(conn.parameters.From); // who canceled the call
				conn.status // => "closed"
		});

		Twilio.Device.connect(function (conn) {
				// Called for all new connections
				console.log(conn.status);
		});

		Twilio.Device.disconnect(function (conn) {
				// Called for all disconnections
				console.log(conn.status);
		});

		Twilio.Device.error(function (e) {
				console.log(e.message + " for " + e.connection);
		});

		Twilio.Device.incoming(function(connection) {
			connection.accept();
			console.log('connection established');
			// do awesome ui stuff here
			// $('#call-status').text("you're on a call!");
		});

		$("#hangup").click(function() {
				Twilio.Device.disconnectAll();
		});
}

//------------------------------------------------------------------------------
function sortCalls(table, $index) {
	/* @arg column: column number
	 */

	var column = $index + 1;

  var tbody = table.find('tbody');

  var $th = $('th:nth-child(' + column + ')');
  var is_ascending = HTMLEncode($th.text()).indexOf(window.unicode['DOWN_ARROW']) > -1;

  if(is_ascending)
    var sort_by = 'descending';
  else
    var sort_by = 'ascending';
   
  var num_a = 0;
  // Clear existing sort arrows 
  $('th a').each(function () {
		num_a++;
    var html = HTMLEncode($(this).text());

    html = html.replace(window.unicode['UP_ARROW'], '');
    html = html.replace(window.unicode['DOWN_ARROW'], '');
    html = html.replace(window.unicode['SPACE'], ' ');
		html = html.replace(/&#[0-9][0-9];/g, '');

    $(this).text(html);
  });

  // Add sort arrow
  var $a = $('a', $th);

  if (sort_by == 'ascending')
    $a.html($a.html() + window.unicode['DOWN_ARROW']);
  else 
    $a.html($a.html() + window.unicode['UP_ARROW']);

  // Sort rows
  $sorted_rows = tbody.find('tr').sort(function (a, b) {
    var nth_child = 'td:nth-child(' + column + ')';

    if (sort_by == 'ascending')
      return $(nth_child, a).text().localeCompare($(nth_child, b).text());
    else
      return $(nth_child, b).text().localeCompare($(nth_child, a).text());
  });

	tbody.empty();
	$sorted_rows.appendTo(tbody);

	loadTooltip();
	enableEditableFields();
	addDeleteBtnHandlers();
}

//------------------------------------------------------------------------------
function enableEditableFields() {
  $("td").on('click',function() {      
    $cell = $(this);

    // Editable fields are assigned 'name' attribute
    var name = $cell.attr('name');

    if(!name)
      return;

		if(name.indexOf('udf') == -1)
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
		$input.focus();

		$input.keyup(function(event) {
				if(event.keyCode == 13){
						saveFieldEdit($cell, $input);
				}
		});
  
    // Save edit to DB when focus lost, remove <input> element 
    $input.blur(function() {
				saveFieldEdit($cell, $input);
    });

  });
}

//------------------------------------------------------------------------------
function saveFieldEdit($cell, $input) {
		$cell.html($input.val());
		var field_name = String($cell.attr('name'));

		console.log(field_name + ' edited');

		var payload = {};
		payload[field_name] = $input.val();

		if($input.val() == '---')
			return;

		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'notify/' + $cell.parent().attr('id') + '/edit',
			data: payload
		}).done(function(msg) {
				if(msg != 'OK') {
					alertMsg(msg, 'danger');
					$cell.html(text);
				}
				else {
						alertMsg('Edited field successfully', 'success');
				}
		});

		$input.focus();
}

//------------------------------------------------------------------------------
function updateJobStatus() {
  if($('#event-status').text() == 'In Progress') {
      var sum = 0;
      var n_sent = 0;
      var n_incomplete = 0;

      $('[name="voice_sms_status"]').each(function() {
        sum++;

        if($(this).text().indexOf('Sent') > -1)
          n_sent++;
        else
          n_incomplete++;
      });

      var delivered_percent = Math.floor((n_sent / sum) * 100);
      $('#event-summary').text((String(delivered_percent) + '%'));
  }
}

//------------------------------------------------------------------------------
function updateCountdown() {
  /* Display timer counting down until event_datetime */

  $summary_lbl = $('#event-summary');

	// remove last 6 char offset ("-06:00") so Date.parse() will work
	var date_str = $('#scheduled_datetime').text();
	date_str = date_str.substring(0, date_str.length-6);
  var scheduled_date = Date.parse(date_str);
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
  
  $summary_lbl.text('');

  if(Math.floor(diff_days) > 0)
    $summary_lbl.text(Math.floor(diff_days) + ' Days ');

  $summary_lbl.text($summary_lbl.text() + Math.floor(diff_hrs) + ' Hours ' + Math.floor(diff_min) + ' Min ' + Math.floor(diff_sec) + ' Sec');
}

//------------------------------------------------------------------------------
function enableColumnSorting() {
	// Enable sorting on column headers
	$('th').each(function($index){
			var $a = $('a', $(this));
			$a.text($a.text().toTitleCase());

			var encoded_text = HTMLEncode($a.text());

			if(encoded_text.indexOf(window.unicode['DOWN_ARROW']) > -1)
					$a.attr('title', 'Sort Descending Order');
			else  
					$a.attr('title', 'Sort Ascending Order');

			$a.click(function() {
					var id = $(this).parent().attr('id');
					
					sortCalls($('#notific-table'), $index);
					var encoded_text = HTMLEncode($(this).text());

					if(encoded_text.indexOf(window.unicode['DOWN_ARROW']) > -1)
							$(this).attr('title', 'Sort Descending Order');
					else
							$(this).attr('title', 'Sort Ascending Order');
				});
	});
}


//------------------------------------------------------------------------------
function applyStatusColor($td) {
  var status = $td.text().toLowerCase();

	if(status == '<hr>' || !status || status == "")
		$td.html('<hr>');

  if(status == 'pending')
      $td.css('color', window.colors['DEFAULT']);
  else if(['completed', 'delivered'].indexOf(status) > -1)
      $td.css('color', window.colors['SUCCESS']);
  else if(['queued', 'busy', 'no-answer'].indexOf(status) > -1)
      $td.css('color', window.colors['IN_PROGRESS']);
  else if(['failed', 'cancelled'].indexOf(status) > -1)
      $td.css('color', window.colors['FAILED']);
}

//------------------------------------------------------------------------------
function formatColumns() {
    var $a_child = $('th:first-child a');
    $a_child.html($a_child.html()+window.unicode['DOWN_ARROW']);

    $('.delete-btn').button({
        icons: {
          primary: 'ui-icon-trash'
        },
        text: false
    })

		$('[name="email"]').each(function() {
				if($(this).text() == '<hr>')
					$(this).html("<hr>");
		});

    $('[name="phone"]').each(function() {
        if($(this).text() == '<hr>') {
						$(this).html("<hr>");
            return;
				}

        // convert intl format to (###) ###-####
        var to = $(this).text();
        to = '('+to.substring(2,5)+') '+to.substring(5,8)+'-'+to.substring(8,12);
        $(this).text(to);
    });

    $('td[name="voice_sms_status"]').each(function() {
        $(this).text($(this).text().toTitleCase());
        applyStatusColor($(this));
    });

    $('td[name="email_status"]').each(function() {
        $(this).text($(this).text().toTitleCase());
        applyStatusColor($(this));
    });

    $('td[name="sms_reply"]').each(function() {
        applyStatusColor($(this));
    });
}
