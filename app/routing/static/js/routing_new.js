
//------------------------------------------------------------------------------
function initRouting() {

    addSocketIOHandlers();
    addEventHandlers();
    prettyFormatting();

    $('#routing-tbl').DataTable({
        responsive:true,
        select:true
    });

    $('#routing-tbl').show();
}

//------------------------------------------------------------------------------
function prettyFormatting() {

  $('td[name="status"]').each(function() {

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
            url: $URL_ROOT + 'api/routing/edit',
            data: {
                'route_id': $(this).parent().parent().attr('id'),
                'field':'depot',
                'value':$(this).find('option:selected').text()}
        })
        .done(function(response) {
            if(response['status'] == 'success')
                alertMsg('Successfully edited depot', 'success');
        });
    });

    $('select[name="drivers"]').change(function() {
        $.ajax({
            type:'POST',
            url: $URL_ROOT + 'api/routing/edit',
            data: {
                'route_id': $(this).parent().parent().attr('id'),
                'field':'driver',
                'value':$(this).find('option:selected').text()}
        })
        .done(function(response) {
            if(response['status'] == 'success')
                alertMsg('Successfully edited driver', 'success');
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

            var route_id = JSON.parse($(this).attr('data-route'))['_id']['$oid'];

            $.ajax({
                context: this,
                type: 'POST',
                url: $URL_ROOT + 'api/routing/build',
                data: {'route_id': route_id}
            })
            .done(function(response) {
            });
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

    $('button[name="warnings_btn"]').each(function() {
		$route_btn = $(this).parent().parent().find('button[name="route_btn"]');

        var warnings = JSON.parse($route_btn.attr('data-route'))['routific']['warnings'];
        var errors = JSON.parse($route_btn.attr('data-route'))['routific']['errors'];
				
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
    socket = io.connect('https://' + document.domain + ':' + location.port);

    socket.on('connect', function(){
        console.log('socket.io connected!');

        socket.on('joined', function(response) {
            console.log(response);
        });
    });

    socket.on('discover_routes', function(data) {
        console.log('discover_routes, status=' + data['status']);

        if(data['status'] == 'in-progress') {
			$('.loader-div label').text('Analyzing Routes');
			$('.loader-div').slideToggle();
			$('.btn.loader').fadeTo('slow', 1);
        }
        else if(data['status'] == 'discovered') {
            addRouteRow(data['route']);
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
			console.log('route completed');

			// TODO: update buttons
		}
	});
}

//------------------------------------------------------------------------------
function addRouteRow(route) {
		/* Columns:[Date Block Orders Size New Depot Driver Status Length Command 
			 Sheet Geocoding]
		*/

    var $row = 
      '<tr style="display:none" id="'+route['_id']['$oid']+'">' +
        '<td>' + new Date(route['date']['$date']).toDateString() + '</td>' +
        '<td>' + route['block'] + '</td>' +
        '<td>' + route['routific']['nOrders'] + '</td>' +
        '<td>' + route['stats']['nBlockAccounts'] + '</td>' +
        '<td>' + route['stats']['nDropoffs'] + '</td>' +
        '<td>' + $('#routing-tbl tbody tr:first td[name="depots"]').html() + '</td>' +
        '<td>' + $('#routing-tbl tbody tr:first td[name="drivers"]').html() + '</td>' +
        '<td>' + route['routific']['status'] + '</td>' +
        '<td>' + (route['routific']['totalDuration'] || '-- : --') + '</td>' +
        '<td><button name="route_btn" id="" class="btn btn-outline-primary">Route</button></td>' +
        '<td></td>' + //<button id="" class="btn btn-outline-primary">View</button></td>' +
        '<td></td>'; //' + (route['warnings'] || '') + '</td>';

    $('#routing-tbl tbody').append($row);
    $('#routing-tbl tbody tr:last').fadeIn('slow');
}
