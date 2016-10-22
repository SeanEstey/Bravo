
//------------------------------------------------------------------------------
function init() {
		setupTwilioClient();
    addBravoTooltip();
    enableEditableFields();
		enableColumnSorting();
		formatColumns();
    buildAdminPanel();
    addBtnHandlers();
    addSocketIOHandlers();

    var $a_child = $('th:first-child a');
    $a_child.html($a_child.html()+window.unicode['DOWN_ARROW']);

    $('.delete-btn').button({
        icons: {
          primary: 'ui-icon-trash'
        },
        text: false
    })

    if($('.status-banner').text()) {
        bannerMsg($('.status-banner').text(), 'info', 15000);
    }
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    console.log('attempting socket.io connection to ' + socketio_url + '...');

    var socket = io.connect(socketio_url);

    socket.on('connect', function(){
        socket.emit('connected');
        console.log('socket.io connected!');
    });

    socket.on('notific_status', function(data) {
        console.log('received msg!');
        console.log(JSON.stringify(data));

        // Find "status" column for notification
        var notific_id = data['notific_id'];
        //$('td
        //receiveMsgUpdate(data);
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
function addBtnHandlers() {
    //if($('#event-status').text().indexOf('Pending') > -1) {
      var args =  window.location.pathname.split('/');
      var evnt_id = args.slice(-1)[0];

      $('.delete-btn').each(function(){ 
          $(this).click(function() {
              var acct_id = $(this).attr('id');
              var $tr = $(this).parent().parent();

              $.ajax({
                type: 'POST',
		            url: $URL_ROOT + 'notify/' + evnt_id + '/' + acct_id + '/remove'
              }).done(function(msg) {
                console.log('%s notifications removed', msg);

                if(msg == 'OK'){ 
                  $tr.remove();
                  bannerMsg('Notification removed', 'info');
                }
                else
                  bannerMsg(msg, 'error');
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
   
    // Add admin_mode pane buttons

    // Add btns to fire each event trigger. trig_ids are stored in data-container 
    // "Status" columns i.e. "Voice SMS Status"
    $('th[id] a:contains("Status")').parent().each(function() {
        console.log('adding fire btn for trig_id ' + $(this).attr('id'));

        var col_caption = $(this).children().text();

        if(col_caption.search("Email") > -1) {
          var btn_caption = 'Send Emails Now';
          var btn_id = 'fire-voice-sms-btn';
        }
        else if(col_caption.search("Voice") > -1) {
          var btn_caption = 'Send Voice/SMS Now';
          var btn_id = 'fire-voice-sms-btn';
        }

        btn = addAdminPanelBtn(
          'admin_pane',
          btn_id,
          btn_caption,
          'btn-info', {
            'trig_id':$(this).attr('id')
          }
        );

        btn.click(function() {
            $.ajax({
              context: this,
              type: 'POST',
              url: $URL_ROOT + 'notify/' + $(this).data('trig_id') + '/fire'
            })
            .done(
              function(response, textStatus, jqXHR) {
                  response = JSON.parse(response);

                  console.log('request status: %s', response['status']);

                  if(response['status'] == 'OK') {
                      bannerMsg('Request authorized. Sending notifications...',
                                'info');

                      $(this).addClass('btn btn-primary disabled');
                  }
              }
            );
        });
    });

    stop_btn = addAdminPanelBtn(
      'admin_pane',
      'stop_btn',
      'Stop All',
      'btn-danger');
    
    // Add dev_mode admin pane buttons

    var args =  window.location.pathname.split('/');
    var evnt_id = args.slice(-1)[0];

    reset_btn = addAdminPanelBtn(
      'dev_pane',
      'reset_btn',
      'Reset All');

    reset_btn.click(function() {
      $.ajax({
				type: 'GET',
				url: $URL_ROOT + 'notify/' + evnt_id + '/reset'
			})
			.done(function(response, textStatus, jqXHR) {
				window.location.reload();
			});
    });

    /*
		$('#duplicate-acct').click(function() {
				$.ajax({
					type: 'GET',
					url: $URL_ROOT + 'notify/' + evnt_id + '/dup_acct'}
				).done(function(response, textStatus) {
					window.location.reload();}
				);
		});*/

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Show Debug Info',
      'btn-info');

    show_debug_info_btn.click(function() {
        console.log('not implemented yet');
        //window.location.assign($URL_ROOT + 'summarize/' + String(evnt_id));
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
function sortCalls(table, column) {
	/* @arg column: column number
	 */

	console.log('Sorting notifications by column %s', column);

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

    $(this).text(html);
  });

  // Add sort arrow
  var $a = $('a', $th);

  if (sort_by == 'ascending')
    $a.html($a.html() + window.unicode['DOWN_ARROW']);
  else 
    $a.html($a.html() + window.unicode['UP_ARROW']);

  // Sort rows
  tbody.find('tr').sort(function (a, b) {
    var nth_child = 'td:nth-child(' + column + ')';

    if (sort_by == 'ascending')
      return $(nth_child, a).text().localeCompare($(nth_child, b).text());
    else
      return $(nth_child, b).text().localeCompare($(nth_child, a).text());
  }).appendTo(tbody);
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
  
    // Save edit to DB when focus lost, remove <input> element 
    $input.blur(function() {
      $cell.html($input.val());
      var field_name = String($cell.attr('name'));

      console.log(field_name + ' edited');

      var payload = {};
      payload[field_name] = $input.val();

      if($input.val() == '---')
        return;

      console.log(payload);

      $.ajax({
        type: 'POST',
        url: $URL_ROOT + 'notify/' + $cell.parent().attr('id') + '/edit',
        data: payload
			}).done(function(msg) {
          if(msg != 'OK') {
						bannerMsg(msg, 'error');
            $cell.html(text);
          }
					else {
							bannerMsg('Edited field successfully', 'info');
					}
      });

      $input.focus();
    });
  });
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
function receiveMsgUpdate(data) {
  // Clear the countdown timer if it is running
  if(window.countdown_id)
    clearInterval(window.countdown_id);

  if(typeof data == 'string')
    data = JSON.parse(data);

  console.log('received update: ' + JSON.stringify(data));
  var $row = $('#'+data['id']);
 
  // Update to CALL state 
  if('voice_sms_status' in data) {
    $lbl = $row.find('[name="voice_sms_status"]');
    var caption = data['voice_sms_status'];
    
    if(data['voice_sms_status'] == 'completed') {
      $lbl.css('color', window.colors['SUCCESS_STATUS']);

      if(data['answered_by'] == 'human')
        caption = 'Sent Live';
      else if(data['answered_by'] == 'machine')
        caption = 'Sent Voicemail';
    }
    else if(data['voice_sms_status'] == 'failed') {
      $lbl.css('color', window.colors['FAILED_STATUS']);

      if('error_msg' in data)
        caption = 'Failed (' + data['error_msg'] + ')';
      else
        caption = 'Failed';
    }
    else if(data['voice_sms_status'] == 'busy' || data['voice_sms_status'] == 'no-answer')
      caption += ' (' + data['attempts'] + 'x)';
    else {
      $lbl.css('color', window.colors['IN_PROGRESS_STATUS']);
    }

    $lbl.html(caption.toTitleCase()); 
  }
  // Update to EMAIL state
  else if('email_status' in data) {
    $lbl = $row.find('[name="email_status"]');
    var caption = data['email_status'];
    
    if(data['email_status'] == 'delivered') {
      $lbl.css('color', window.colors['SUCCESS_STATUS']);
    }
    else if(data['email_status'] == 'bounced' || data['email_status'] == 'dropped') {
      $lbl.css('color', window.colors['FAILED_STATUS']);
    }
    else if(data['email_status'] == 'queued') {
      $lbl.css('color', window.colors['IN_PROGRESS_STATUS']);
    }
    else if(data['email_status'] == 'no_email') {
      $lbl.css('color', window.colors['DEFAULT_STATUS']);
    }
    
    $lbl.text(caption.toTitleCase()); 
  }

  if('speak' in data) {
    var title = 'Msg: ' + data['speak'];
    $row.find('[name="voice_sms_status"]').attr('title', title);
  }

  updateJobStatus();
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
	$('th').each(function(){
			var $a = $('a', $(this));
			var encoded_text = HTMLEncode($a.text());

			if(encoded_text.indexOf(window.unicode['DOWN_ARROW']) > -1)
					$a.attr('title', 'Sort Descending Order');
			else  
					$a.attr('title', 'Sort Ascending Order');

			$a.click(function() {
					var id = $(this).parent().attr('id');
					var column_number = id.split('col')[1];
					sortCalls($('#show-calls-table'), column_number);
					var encoded_text = HTMLEncode($(this).text());

					if(encoded_text.indexOf(window.unicode['DOWN_ARROW']) > -1)
							$(this).attr('title', 'Sort Descending Order');
					else
							$(this).attr('title', 'Sort Ascending Order');
				});
	});
}

//------------------------------------------------------------------------------
function formatColumns() {
	$('[name="name"]').each(function() {
	});

	$('[name="phone"]').each(function() {
		if($(this).text() != '---') {
        // convert intl format to (###) ###-####
				var to = $(this).text();
				// Format: (780) 123-4567
				to = '('+to.substring(2,5)+') '+to.substring(5,8)+'-'+to.substring(8,12);

				$(this).text(to);
		}
	});

	// "Email" column
	$('tbody [name="email"]').each(function() {
	});

	// "Call Status" column

	$('tbody [name="voice_sms_status"]').each(function() {

			var status = $(this).text();
		
			if(status.indexOf('completed') > -1) {
					if(status.indexOf('human') > -1)
							status = 'Sent Live';
					else if(status.indexOf('machine') > -1)
							status = 'Sent VM';

					$(this).css('color', window.colors['SUCCESS_STATUS']);
			}
			else if(status.indexOf('failed') > -1) {
					$(this).attr('title', '');

					/*I
					var values = status.split(' ');

					status = values[1];

					if(status == 'invalid_number_format')
							status = 'invalid_number';
					else if(status == 'unknown_error')
							status = 'failed';
					*/

					$(this).css('color', window.colors['FAILED_STATUS']);
			}
			else if(status.indexOf('busy') > -1 || status.indexOf('no-answer') > -1) {
					$(this).attr('title', '');

					var values = status.split(' ');

					status = values[0] + ' (' + values[1] + 'x)';

					$(this).css('color', window.colors['INCOMPLETE_STATUS']);
			}
			else if(status.indexOf('pending') > -1) {
					$(this).attr('title', '');
					$(this).css('color', window.colors['DEFAULT_STATUS']);
			}

			$(this).text(status.toTitleCase());
		});

	// "Email Status" column

	$('tbody [name="email_status"]').each(function() {
		var status = $(this).text();
		if(status.indexOf('delivered') > -1) {
			$(this).attr('title', '');
			$(this).css('color', window.colors['SUCCESS_STATUS']);
		}
		else if(status.indexOf('pending') > -1) {
			$(this).attr('title', '');
			$(this).css('color', window.colors['DEFAULT_STATUS']);
		}
		else if(status.indexOf('queued') > -1) {
			$(this).attr('title', '');
			$(this).css('color', window.colors['DEFAULT_STATUS']);
		}
		else if(status.indexOf('no_email') > -1) {
			$(this).attr('title', '');
			$(this).css('color', window.colors['DEFAULT_STATUS']);
		}
		else if(status.indexOf('bounced') > -1 || status.indexOf('dropped') > -1) {
			$(this).css('color', window.colors['FAILED_STATUS']);
		}
		$(this).text(status.toTitleCase());
	});

	$('[name="event_date"]').each(function() {
		var date = Date.parse($(this).html());
		var string = date.toDateString();
		$(this).html(string);
	});
}



//------------------------------------------------------------------------------
function receiveMsgUpdate(data) {
  // Clear the countdown timer if it is running

  if(typeof data == 'string')
    data = JSON.parse(data);

  console.log('received update: ' + JSON.stringify(data));
  var $row = $('#'+data['id']);
 
  // Update to CALL state 
  if('voice_sms_status' in data) {
    $lbl = $row.find('[name="voice_sms_status"]');
    var caption = data['voice_sms_status'];
    
    if(data['voice_sms_status'] == 'completed') {
      $lbl.css('color', window.colors['SUCCESS_STATUS']);

      if(data['answered_by'] == 'human')
        caption = 'Sent Live';
      else if(data['answered_by'] == 'machine')
        caption = 'Sent Voicemail';
    }
    else if(data['voice_sms_status'] == 'failed') {
      $lbl.css('color', window.colors['FAILED_STATUS']);

      if('error_msg' in data)
        caption = 'Failed (' + data['error_msg'] + ')';
      else
        caption = 'Failed';
    }
    else if(data['voice_sms_status'] == 'busy' || data['voice_sms_status'] == 'no-answer')
      caption += ' (' + data['attempts'] + 'x)';
    else {
      $lbl.css('color', window.colors['IN_PROGRESS_STATUS']);
    }

    $lbl.html(caption.toTitleCase()); 
  }
  // Update to EMAIL state
  else if('email_status' in data) {
    $lbl = $row.find('[name="email_status"]');
    var caption = data['email_status'];
    
    if(data['email_status'] == 'delivered') {
      $lbl.css('color', window.colors['SUCCESS_STATUS']);
    }
    else if(data['email_status'] == 'bounced' || data['email_status'] == 'dropped') {
      $lbl.css('color', window.colors['FAILED_STATUS']);
    }
    else if(data['email_status'] == 'queued') {
      $lbl.css('color', window.colors['IN_PROGRESS_STATUS']);
    }
    else if(data['email_status'] == 'no_email') {
      $lbl.css('color', window.colors['DEFAULT_STATUS']);
    }
    
    $lbl.text(caption.toTitleCase()); 
  }

  if('speak' in data) {
    var title = 'Msg: ' + data['speak'];
    $row.find('[name="voice_sms_status"]').attr('title', title);
  }

}
