
//------------------------------------------------------------------------------
function init() {
		buildAdminPanel();
    addSocketIOHandlers();

    $(function() {
        $("td[colspan=12]").find("p").hide();
        $("td[name=warnings]").click(toggleGeocodeWarnings);
    });

		alertMsg('Click on Warnings for each route to view any conflicts resolving addresses', 'info', 15000);
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
function toggleGeocodeWarnings(event) {
    event.stopPropagation();
    var $target = $(event.target);

    if ($target.closest("td").attr("colspan") > 1){
        $target.slideUp();
    } 
    else {
        $target.closest("tr").next().find("p").slideToggle();
    }                    
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
