
//------------------------------------------------------------------------------
function init() {
    var $a_child = $('th:first-child a');

    $a_child.html($a_child.html()+window.unicode['DOWN_ARROW']);

    addBravoTooltip();
    makeCallFieldsClickable();
		enableColumnSorting();
		formatColumns();

    if($('#job-status').text().indexOf('Pending') > -1) {
      var args =  window.location.pathname.split('/');
      var job_uuid = args.slice(-1)[0];

      $('.delete-btn').each(function(){ 
          $(this).button({
            icons: {
              primary: 'ui-icon-trash'
            },
            text: false
          });

          $(this).click(function() {
              var call_uuid = $(this).attr('id');
              var $tr = $(this).parent().parent();

              $.ajax({
                type: 'POST',
								url: $URL_ROOT + '/reminders/' + job_uuid + '/' + call_uuid + '/remove'
							}).done(function(msg) {
									console.log('reminder removed. msg: %s', msg);

									if(msg == 'OK')
										$tr.remove();
							});
          });
      });
    }
    else if($('#job-status').text() == 'In Progress') {
        $('.cancel-call-col').each(function() {
          $(this).hide();
        });
    }
    else if($('#job-status').text() == 'Completed') {
        $('#job-header').removeClass('label-primary');
        $('#job-header').addClass('label-success');
        $('#job-status').text('Completed');
        $('#job-summary').text('');
        $('.delete-btn').hide();
        $('.cancel-call-col').each(function() {
            $(this).hide();
        });

        console.log('job complete!');
    }

    if($('#job-status').text().indexOf('Pending') > -1) {
        updateCountdown();
        window.countdown_id = setInterval(updateCountdown, 1000);
    }

    updateJobStatus();
    
    $('body').css('display','block');

    // Init socket.io
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    console.log('attempting socket.io connection to ' + socketio_url + '...');

    var socket = io.connect(socketio_url);

    socket.on('connect', function(){
        socket.emit('connected');
        console.log('socket.io connected!');
    });

    socket.on('update_msg', function(data) {
        receiveMsgUpdate(data);
    });

    socket.on('update_job', function(data) {
        if(typeof data == 'string')
            data = JSON.parse(data);

        console.log('received update: ' + JSON.stringify(data));

        if(data['status'] == 'in-progress') {
            console.log('in progress!');
            $('#job-status').text('In Progress');
            $('.cancel-call-col').each(function() {
                $(this).hide();
            });
        }
        else if(data['status'] == 'completed') {
            $('#job-header').removeClass('label-primary');
            $('#job-header').addClass('label-success');
            $('#job-status').text('Completed');
            $('#job-summary').text('');

            console.log('job complete!');
        }
          updateJobStatus();
    });

    //  if(location.port == 8080) {
    var args =  window.location.pathname.split('/');
    var job_uuid = args.slice(-1)[0];

    $('#execute-job').click(function() {
			$.ajax({
				type: 'GET',
				url: $URL_ROOT + 'reminders/' + job_uuid + '/send_calls'
			});
    });

    $('#email-job').click(function() {
			$.ajax({
				type: 'GET',
				url: $URL_ROOT + '/reminders/' + job_uuid + '/send_emails'
			});
    });

    $('#reset-job').click(function() {
      $.ajax({
				type: 'GET',
				url: $URL_ROOT + '/reminders/' + job_uuid + '/reset'
			});
    });

    $('#dump').click(function() {
        window.location.assign($URL_ROOT + 'summarize/' + String(job_uuid));
    });
  
  /*else {
    $('#execute-job').hide();
    $('#reset-job').hide();
    $('#dump').hide();
  }*/
}

//------------------------------------------------------------------------------
function sortCalls(table, column) {
	/* @arg column: column number
	 */

	console.log('Sorting reminders by column %s', column);

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
function makeCallFieldsClickable() {
  $("td").on('click',function() {      
    $cell = $(this);

    // Editable fields are assigned 'name' attribute
    var name = $cell.attr('name');

    if(!name)
      return;

    if(name == 'call_status' || name == 'email_status')
      return;

    if($('#job-status').text().indexOf('Pending') < 0)
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

      if($input.val() == '---')
        return;

      console.log(payload);

      $.ajax({
        type: 'POST',
        url: $URL_ROOT + 'reminders/' + $cell.parent().attr('id') + '/edit',
        data: payload
			}).done(function(msg){
          if(msg != 'OK') {
            showDialog($('#dialog'), 'Your edit failed. Please enter a correct value: ' + msg);
            $cell.html(text);
          }
      });

      $input.focus();
    });
  });
}

//------------------------------------------------------------------------------
function updateJobStatus() {
  if($('#job-status').text() == 'In Progress') {
      var sum = 0;
      var n_sent = 0;
      var n_incomplete = 0;

      $('[name="call_status"]').each(function() {
        sum++;

        if($(this).text().indexOf('Sent') > -1)
          n_sent++;
        else
          n_incomplete++;
      });

      var delivered_percent = Math.floor((n_sent / sum) * 100);
      $('#job-summary').text((String(delivered_percent) + '%'));
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
  if('call_status' in data) {
    $lbl = $row.find('[name="call_status"]');
    var caption = data['call_status'];
    
    if(data['call_status'] == 'completed') {
      $lbl.css('color', window.colors['SUCCESS_STATUS']);

      if(data['answered_by'] == 'human')
        caption = 'Sent Live';
      else if(data['answered_by'] == 'machine')
        caption = 'Sent Voicemail';
    }
    else if(data['call_status'] == 'failed') {
      $lbl.css('color', window.colors['FAILED_STATUS']);

      if('error_msg' in data)
        caption = 'Failed (' + data['error_msg'] + ')';
      else
        caption = 'Failed';
    }
    else if(data['call_status'] == 'busy' || data['call_status'] == 'no-answer')
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
    $row.find('[name="call_status"]').attr('title', title);
  }

  updateJobStatus();
}

//------------------------------------------------------------------------------
function updateCountdown() {
  /* Display timer counting down until event_datetime */

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
					var sort_col = id.split('col')[1];
					sortCalls($('#show-calls-table'), sort_col);
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
	// "Name" column
	$('[name="name"]').each(function() {
		$(this).css('width', '125px');
	});

	// "To" column
	$('[name="to"]').each(function() {
		// Make this cell wide enough
		$(this).css('width', '135px');

		if($(this).text() != '---') {
				var to = $(this).text();
				// Strip parentheses, dashes and spaces
				to = to.replace(/[\s\)\(-]/g, '');
				// Format: (780) 123-4567
				to = '('+to.substring(0,3)+') '+to.substring(3,6)+'-'+to.substring(6,11);

				$(this).text(to);
		}
	});

	// "Office Notes" column
	$('tbody [name="office_notes"]').each(function() {
			$(this).css('white-space', 'nowrap');
			$(this).css('overflow', 'hidden');
			$(this).css('text-overflow', 'ellipsis');
	});

	// "Status" column
	$('tbody [name="status"]').each(function() {
			$(this).css('white-space', 'nowrap');
	});

	// "Email" column
	$('thead [name="email"]').css('width', '150px');
	$('tbody [name="email"]').each(function() {
			$(this).css('width', '150px');
			$(this).css('white-space', 'nowrap');
			$(this).css('overflow', 'hidden');
			$(this).css('text-overflow', 'ellipsis');
	});

	// "Call Status" column
	$('thead [name="call_status"]').css('width', '110px');

	$('tbody [name="call_status"]').each(function() {
			$(this).css('width', '110px');

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
	$('thead [name="email_status"]').css('width', '110px');

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
		$(this).css('width', '145px');
		var date = Date.parse($(this).html());
		var string = date.toDateString();
		$(this).html(string);
	});
}
