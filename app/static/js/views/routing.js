
//------------------------------------------------------------------------------
function init() {
		buildAdminPanel();
    addSocketIOHandlers();
    addEventHandlers();
    prettyFormatting();

		//alertMsg('Click on Warnings for each route to view any conflicts resolving addresses', 'info', 15000);
}

//------------------------------------------------------------------------------
function prettyFormatting() {
  $('td[name="status"]').each(function() {
      //console.log($(this).text());

      if($(this).text() == 'pending') {
          $(this).css('color', window.colors['IN_PROGRESS']);
          $(this).text($(this).text().toTitleCase());
      }
      else if($(this).text() == 'finished') {
          $(this).css('color', window.colors['SUCCESS']);
          $(this).text($(this).text().toTitleCase());
      }
  });
}

//------------------------------------------------------------------------------
function addEventHandlers() {
		$('select[name="depots"]').change(function() {
				$.ajax({
					type:'POST',
					url: $URL_ROOT + 'routing/edit/' + $(this).parent().parent().attr('id'),
					data: {'field':'depot', 'value':$(this).find('option:selected').text()}
				})
				.done(function(response) {
						if(response['status'] == 'success')
								alertMsg('Successfully edited depot', 'success');
				});
		
		});

		$('select[name="drivers"]').change(function() {
				$.ajax({
					type:'POST',
					url: $URL_ROOT + 'routing/edit/' + $(this).parent().parent().attr('id'),
					data: {'field':'driver', 'value':$(this).find('option:selected').text()}
				})
				.done(function(response) {
						if(response['status'] == 'success')
								alertMsg('Successfully edited driver', 'success');
				});
		});

    $('button[name="view_btn"]').each(function() {
				var metadata = JSON.parse($(this).parent().parent().find('button[name="route_btn"]').attr('data-route'));
				
				if(!metadata['ss_id']) {
						$(this).prop('disabled', true);
						return;
				}

				$(this).show();
				$(this).prev().hide();

				$(this).click(function() {
						window.open("https://docs.google.com/spreadsheets/d/"+metadata['ss_id']);
				});
		});

    $('button[name="route_btn"]').each(function() {
        var metadata = JSON.parse($(this).attr('data-route'));
				
				if(metadata['job_id']) {
						$(this).text('Reroute');
				}

				$(this).click(function() {
						$('.loader-div label').text('Building Route');
						$('.loader-div').slideToggle(function() {
								$('.btn.loader').fadeTo('slow', 1);
						});

						$.ajax({
							context: this,
							type: 'GET',
							url: $(this).attr('href')
						})
						.done(function(response) {
						});
				});
		});

    $('button[name="warnings_btn"]').each(function() {
				$route_btn = $(this).parent().parent().find('button[name="route_btn"]');

        var warnings = JSON.parse($route_btn.attr('data-route'))['warnings'];
        var errors = JSON.parse($route_btn.attr('data-route'))['errors'];
				
				if(warnings == undefined) {
					$(this).prop('disabled', true);
					return;
				}

				if(warnings.length > 0 || errors.length > 0) {
						$(this).show();
						$(this).prev().hide();

						var n = warnings.length + errors.length;
						if(n == 1)
								$(this).text("1 issue");
						else
								$(this).text(String(n) + " issues");

						$(this).switchClass('btn-outline-primary', 'btn-outline-danger');
				}
				else
						$(this).text('0 Issues');

        $(this).click(function() {
            $modal = $('#warnings_modal');
            $modal.find('.modal-title').text('Geocode Issues');
            $modal.find('.modal-body').html('');

						var html = "<div class='alert alert-warning' role='alert'><strong>Warnings</strong>";
            html +=      "<ol>";

            for(var i=0; i<warnings.length; i++) {
                html += '<li>'+warnings[i]+'</li>';
            }

            html += "</ol>";
						html += "</div>";

						if(errors.length > 0) {
								html += "<div class='alert alert-danger' role='alert'><strong>Errors</strong>";
								html +=   "<ol>";

								for(var i=0; i<errors.length; i++) {
										html += '<li>'+errors[i]+'</li>';
								}

								html +=   "</ol>";
								html += "</div>";
						}

            $modal.find('.modal-body').append(html);
            $modal.modal('show');
        });
    });
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    var socket = io.connect(socketio_url);

    socket.on('connect', function(){
        console.log('socket.io connected!');
        socket.emit('join', {});
    });

    socket.on('room_msg', function(data) {
        console.log('room msg: ' + JSON.stringify(data));
    });

    socket.on('analyze_routes', function(data) {
        console.log('analyze_routes, status=' + data['status']);
        //console.log(data);
        //console.log('analyze_routes status: %s', data['status']);

        if(data['status'] == 'in-progress') {
						$('.loader-div label').text('Analyzing Routes');
						$('.loader-div').slideToggle();
						$('.btn.loader').fadeTo('slow', 1);
        }
        else if(data['status'] == 'completed') {
            $('.btn.loader').fadeTo('slow', 0, function() {
                $('.loader-div').slideUp();//Toggle();
            });
        }
    });

		socket.on('route_status', function(data) {
				if(data['status'] == 'completed') {
            $('.btn.loader').fadeTo('slow', 0, function() {
                $('.loader-div').slideToggle();
            });
	
						// TODO: update buttons
						// data['ss_id']
						// data['warnings']
				}
		});

    socket.on('add_route_metadata', function(data) {
        if(data['agency'] != $AGENCY)
          return;

        console.log('received route metadata');
        addRouteRow(data);
    });
}

//------------------------------------------------------------------------------
function addRouteRow(route) {
    var $row = 
      '<tr style="display:none" id="'+route['_id']['$oid']+'">' +
        '<td>' + new Date(route['date']['$date']).toDateString() + '</td>' +
        '<td>' + route['block'] + '</td>' +
        '<td>' + route['orders'] + '</td>' +
        '<td>' + route['block_size'] + '</td>' +
        '<td>' + route['dropoffs'] + '</td>' +
        '<td>' + $('#routing-tbl tbody tr:first td[name="depots"]').html() + '</td>' +
        '<td>' + $('#routing-tbl tbody tr:first td[name="drivers"]').html() + '</td>' +
        '<td>' + route['status'] + '</td>' +
        '<td>' + (route['duration'] || '-- : --') + '</td>' +
        '<td><button name="route_btn" id="" class="btn btn-outline-primary">Route</button></td>' +
        '<td><button id="" class="btn btn-outline-primary">View</button></td>' +
        '<td>' + route['warnings'] + '</td>';

    $('#routing-tbl tbody').append($row);
    $('#routing-tbl tbody tr:last').fadeIn('slow');
}

//------------------------------------------------------------------------------
function buildAdminPanel() {
    // dev_mode pane buttons
    $('#admin_pane').hide();

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Debug Mode',
      'btn-outline-primary');

		// Prints Routific job_id to console
    show_debug_info_btn.click(function() {
				$(this).prop('disabled', 'true');

				$('#routing-tbl th:last').after('<th width="5%">Debug</th>');

				$('tr[id]').each(function() {
            if(! $(this).attr('id'))
                return;

						var $debug_btn = 
							'<button name="debug-btn" ' +
                      'id="' + $(this).attr('id') + '"' +
											'class="btn btn-outline-warning">Print</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
								$route_btn = $(this).parent().parent().find('button[name="route_btn"]');

								console.log(JSON.parse($route_btn.attr('data-route')));

								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Metadata</b> buttons prints notification info to console.', 'info');
    });
}
