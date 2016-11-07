
//------------------------------------------------------------------------------
function init() {
		buildAdminPanel();
    addSocketIOHandlers();
    addEventHandlers();
    prettyFormatting();

		alertMsg('Click on Warnings for each route to view any conflicts resolving addresses', 'info', 15000);
}


//------------------------------------------------------------------------------
function prettyFormatting() {
  $('td[name="status"]').each(function() {
      console.log($(this).text());

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
    $('button[name="route_btn"]').on('click', function(event) {
        $.ajax({
          context: this,
          type: 'GET',
          url: $(this).attr('href')
        })
        .done(function(response) {
            console.log(response);
        });
        console.log($(this).attr('href'));

    });

    $('button[name="warnings_btn"]').each(function() {
        if(!$(this).attr('data-warnings')) {
          
            $(this).prop('disabled', true);
            $(this).hide();
            return;
        }

        var warnings = JSON.parse($(this).attr('data-warnings'));
        $(this).text(String(warnings.length) + " Warnings");


        $(this).click(function() {
            $modal = $('#warnings_modal');
            $modal.find('.modal-title').text('Warnings');
            $modal.find('.modal-body').html('');

            var warnings = JSON.parse($(this).attr('data-warnings'));

            var html = "<ol>";

            for(var i=0; i<warnings.length; i++) {
                html += '<li>'+warnings[i]+'</li>';
            }

            html += "</ol>";

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
        socket.emit('connected');
        console.log('socket.io connected!');
    });

    socket.on('analyze_routes', function(data) {
        console.log('analyze_routes status: %s', data['status']);

        if(data['status'] == 'in-progress') {
        }
        else if(data['status'] == 'completed') {
            $('.btn.loader').fadeTo('slow', 0, function() {
                $('.loader-div').slideToggle();
            });
        }
    });

    socket.on('add_route_metadata', function(data) {
        console.log('received route metadata');
        addRouteRow(data);
    });

    socket.on('route_status', function(data) {

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
        '<td>' + route['geocode_warnings'] + '</td>' +
        '<td><button id="" class="btn btn-outline-primary">Build Route</button></td>' +
        '<td><button id="" class="btn btn-outline-primary">View</button></td>';

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

				$('#routing-tbl th:last').after('<th width="10%">DEBUG</th>');

				$('tr[id]').each(function() {
            if(! $(this).attr('id'))
                return;

						var $debug_btn = 
							'<button name="debug-btn" ' +
                      'id="' + $(this).attr('id') + '"' +
											'class="btn btn-warning">Print Debug</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
                $.ajax({
                  context: this,
                  type: 'GET',
                  url: 'https://api.routific.com/jobs/' + $(this).attr('id')
                })
                .done(function(response) {
                    //console.log(JSON.parse(response));
                    console.log(response);
                });

								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Debug</b> buttons prints notification info to console.', 'info');
    });

    analyze_routes_btn = addAdminPanelBtn(
      'dev_pane',
      'analyze_routes_btn',
      'Analyze Routes',
      'btn-outline-primary');

    analyze_routes_btn.click(function() {
       $.ajax({
          context: this,
          type: 'GET',
          url: $URL_ROOT + '/test_analyze_routes/3'
      })
      .done(function(response) {
          $('.loader-div').slideToggle(function() {
              $('.btn.loader').fadeTo('slow', 1);
          });
      });
    });
}
