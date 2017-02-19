//------------------------------------------------------------------------------
function event_list_init() {
	loadTooltip();
	buildAdminPanel();
	addDeleteBtnHandlers();
	addSocketIOHandlers();
	addPageNavHandlers();

  $('#new_event').click(function() {
      $('#new_event_modal').modal('show');
  });
}

//------------------------------------------------------------------------------
function addPageNavHandlers() {
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
}

//------------------------------------------------------------------------------
function addDeleteBtnHandlers() {

    $('.delete-btn').click(function(){ 
				var $tr = $(this).parent().parent();
				var event_uuid = $tr.attr('id');

				console.log('prompt to delete job_id: ' + event_uuid);

				$('#mymodal .modal-title').text('Confirm');
				$('#mymodal .modal-body').html('');
				$('#mymodal .modal-body').text('Really delete this job?');
				$('#mymodal .btn-secondary').text('No');
				$('#mymodal .btn-primary').text('Yes');

				// Clear any currently bound events
				$('#mymodal .btn-primary').off('click');

				$('#mymodal .btn-primary').click(function() {
						$.ajax({
							type: 'POST',
							url: $URL_ROOT + 'api/notify/events/cancel',
              data: {'evnt_id': event_uuid}
						})
						.done(function(response) {
								if(response['status'] == 'success')
										$tr.remove();
						});

						$('#mymodal').modal('hide'); 
				});

				$('#mymodal').modal('show');
		});
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {
    socket = io.connect('https://' + document.domain + ':' + location.port);

    socket.on('connect', function(){
        console.log('socket.io connected!');

        socket.on('joined', function(response) {
            console.log(response);
        });
    });

    socket.on('test', function(data){
        console.log('test! data='+data);
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
function buildAdminPanel() {
		$('#admin_pane').hide();

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Debug Mode',
      'btn-outline-primary');

		// Add debug buttons that print notific['tracking'] data to console
    show_debug_info_btn.click(function() {
				$(this).prop('disabled', 'true');

				$('#events_tbl th:last').after('<th>Debug</th>');

				$('tr[id]').each(function() {
						var $debug_btn = 
							'<button name="debug-btn" ' +
											'class="btn btn-outline-warning">Print</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);

								$.ajax({
									type: 'post',
									url: $URL_ROOT + 'notify/' + $(this).parent().parent().attr('id') + '/debug_info'
							  })
								.done(function(response) {
										console.log(response);
								});
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Debug</b> buttons prints notification info to console.', 'info');
    });

}


//------------------------------------------------------------------------------
function displayTrig(trig) {
		if(trig == undefined)
				return "<td><hr></td><td><hr></td>";

		trig['fire_dt'] = new Date(trig['fire_dt']['$date']);

		if(trig['status'] == 'fired') {
				var lbl = 'Sent';
				var color = 'green';	
		}
		else {
				var lbl = 'Pending';
				var color = 'blue';
		}
		
		return "" +
			"<td>" +
				"<font color='"+ color +"'>"+ lbl + "</font> @ " +
				trig['fire_dt'].strftime('%b %d, %I:%M %p') +
			"</td>" + 
			"<td>"+ trig['count'] +"</td>";
}

//------------------------------------------------------------------------------
function addEvent(evnt, view_url, cancel_url, desc) {

	evnt['event_dt'] = new Date(evnt['event_dt']['$date']);

	var tr = 
		"<tr id='" +evnt['_id']['$oid']+ "'>"+
			"<td name='event_name'>"+
				"<a class='hover' href='"+ view_url +"'>"+evnt['name']+"</a>"+ 
			"</td>"+
			"<td>"+ 
				"<a class='hover' href='"+ view_url +"'>"+evnt['event_dt'].toDateString()+"</a>"+ 
			"</td>"+
			displayTrig(evnt['triggers'][0])+
			displayTrig(evnt['triggers'][1])+
			"<td>"+
				"<button "+ 
					 "data-toggle='tooltip' "+
					 "class='ui-button ui-widget ui-corner-all ui-button-icon-only delete-btn' "+
					 "type='button' "+
					 "id='"+ cancel_url +"' "+ 
					 "title='Delete this event' "+
					 "name='delete-btn'>"+
					 "<span class='ui-button-icon-primary ui-icon ui-icon-trash'></span>"+
				"</button>"+
			"</td>"+
		"</tr>";

	console.log(tr);

	$('#events_tbl tbody').append(tr);
	$('#events_tbl tbody tr:last').fadeIn('slow');

	addDeleteBtnHandlers();

	alertMsg(desc, 'success');
}
