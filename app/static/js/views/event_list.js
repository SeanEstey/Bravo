
//------------------------------------------------------------------------------
function init() {
	loadTooltip();
	buildAdminPanel();
	addDeleteBtnHandlers();
	addSocketIOHandlers();
	addPageNavHandlers();
	showAdminServerStatus();
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

				$('.modal-title').text('Confirm');
				$('.modal-body').html('');
				$('.modal-body').text('Really delete this job?');
				$('#btn-secondary').text('No');
				$('#btn-primary').text('Yes');

				// Clear any currently bound events
				$('#btn-primary').off('click');

				$('#btn-primary').click(function() {
						$.ajax({
							type: 'GET',
							url: $URL_ROOT + 'notify/'+event_uuid+'/cancel'
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
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    var socket = io.connect(socketio_url);

    socket.on('connect', function(){
        socket.emit('connected');
        console.log('socket.io connected!');
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

		addAdminPanelBtn(
			'dev_pane',
			'schedule-btn',
			'Schedule Block',
      'btn-outline-primary'
		)
		.click(function() {
        $('.modal-title').text('Schedule Block');

				var form = "<input width='100%' id='block' class='input' name='block' type='text'/>";

				$('.modal-body').html(form);

				$("#block").keyup(function(event){
						if(event.keyCode == 13){
								console.log('enter key');
								$("#btn-primary").click();
						}
				});

        $('#btn-secondary').text('Cancel');
        $('#btn-primary').text('Schedule');

				$('#mymodal').on('shown.bs.modal', function () {
					$('#block').focus()
				})

				$('#mymodal').modal();

				// Clear any currently bound events
				$('#btn-primary').off('click');

        $('#btn-primary').click(function() {
						if(!$('#block').val())
								return;

            $('#mymodal').modal('hide'); 

						var block = $('#block').val();
						$('.modal-body').html('');

						$('.loader-div').slideToggle(function() {
								$('.btn.loader').fadeTo('slow', 1);
						});

						$.ajax({
							context: this,
							type: 'POST',
							url: $URL_ROOT + 'notify/'+block+'/schedule'
						})
						.done(function(response) {
								if(response['status'] != 'OK') {
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
				});
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
