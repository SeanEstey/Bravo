
//---------------------------------------------------------------------
function booker_init() {
    alertMsg(
      'Enter an account ID, address, or postal code below',
      'info', 30000
    );
    
    buildAdminPanel();
    addSocketIOHandlers();
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {
    var socketio_url = 'http://' + document.domain + ':' + location.port;

    var socket = io.connect(socketio_url);

    socket.on('connected', function(data){
        $AGENCY = data['agency'];
        console.log('socket.io connected! agency: ' + data['agency']);
    });

    socket.on('update_maps', function(data) {
        console.log(data['description']);
        alertMsg(data['description'], 'success');
    });
}

//---------------------------------------------------------------------
function validate(field_id) {
    var element = document.getElementById(field_id);  
    
    // Some browsers (Safari) do not evaluate <input pattern> property. 
    // Manually test regular expression
    if(element.pattern) {
      var pattern = new RegExp(element.pattern);
      
      if(!pattern.test(element.value)) {
        element.style.border = '1px solid red';
        element.value = '';
        element.placeholder = 'Invalid value';
        return false;
      }
    }
 
    return true;
}

//---------------------------------------------------------------------
function search(form) {  
    var search_value = form.elements['search_box'].value;
    
    form.elements['search_box'].value = '';
    
    if(!search_value) {
      return false;
    }

    console.log('Starting search for: ' + search_value);

    $('#results').show();
    $('#search-loader').slideToggle(function() {
        $('#search-loader .btn.loader').fadeTo('fast', 1);
    });

		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'booker/search',
			data: {'query':search_value},
			dataType: 'json'
		})
		.done(function(response) {
        console.log(response);

				if(response['status'] != 'success') {
						alertMsg(
							'Response: ' + response['description'], 
							'danger', 30000
            );

						$('#search-loader .btn.loader').fadeTo('fast', 0, function() {
								$('#search-loader').slideToggle();
						});

						return;
				}

        displaySearchResults(response);
    })
}

//---------------------------------------------------------------------
function displaySearchResults(response) {
    $('#search-loader .btn.loader').fadeTo('slow', 0, function() {
        $('#search-loader').slideUp();
    });

    alertMsg(response['description'], 'success', -1);

    for(var i=0; i<response['results'].length; i++) {
        var result = response['results'][i];
        var $row = 
          '<tr style="background-color:white">' + 
            '<td name="date">' + result['event']['start']['date'] + '</td>' +
            '<td name="block">' + result['name'] + '</td>' +
            '<td>' + result['event']['summary'].slice(
              result['event']['summary'].indexOf('[')+1,
              result['event']['summary'].indexOf(']')) + '</td>' +
            '<td name="postal">' + result['event']['location'] + '</td>' +
            '<td>' + result['booked'] + '</td>' +
            '<td>' + '100' + '</td>' +
            '<td>' + result['distance'] + '</td>' +
            '<td style="width:6%; text-align:right"> ' +
              '<button ' +
                'name="book_btn"'+
                'class="btn btn-outline-primary"' +
                '>Book' +
              '</button>' +
            '</td>' +
          '</tr>';
        $('#results tbody').append($row);

        // save account info in button data
        if(response.hasOwnProperty('account')) {
            $('#results tr:last button').data('aid', response['account']['id']);
            $('#results tr:last button').data('name', response['account']['name']);
        }
    }

    $('button[name="book_btn"]').click(function() {
        console.log($(this).data('aid'));
        $tr = $(this).parent().parent();

        showBookingModal(
          $tr.find('[name="block"]').text(),
          $tr.find('[name="date"]').text(),
          $tr.find('button').data('aid'),
          $tr.find('button').data('name')
        )
    });
}

//---------------------------------------------------------------------
function showBookingModal(block, date, aid, name) {
    $modal = $('#mymodal');
    $modal.find('.modal-title').text('Confirm Booking');

    $('#mymodal .modal-body').html($('#booking_options').html());
    $modal.find('.modal-body').find('#booking_options').show();

    $modal.find('label[name="name"]').html('Account Name: <b>' + name + '</b>');
    $modal.find('label[name="block"]').html('Block: <b>' + block + '</b>');
    var date = new Date(date);
    $modal.find('label[name="date"]').html('Date: <b>' + date.strftime('%B %d %Y') + '</b>');
    
    $('#mymodal .btn-primary').text('Book');
    $('#mymodal .btn-primary').click(function() {
        requestBooking(aid, block, date);
    });
  
    $modal.modal('show');
}
  
//---------------------------------------------------------------------
function requestBooking(aid, block, date, notes) {
    console.log('request booking');

    $('#mymodal').find('#booker-loader').show();
    $('#mymodal').find('.btn.loader').fadeTo('fast', 1);

    /*

		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'booker/book',
			data: {
        'block': block,
        'date': date,
        'id': aid,
        'driver_notes': notes
      },
			dataType: 'json'
		})
		.done(function(response) {
        $('#booker-loader').fadeOut('fast');
        console.log(response);
    });
    */
}
  
  
//---------------------------------------------------------------------
function searchKeyPress(e) {
    // look for window.event in case event isn't passed in
    e = e || window.event;
    if (e.keyCode == 13) {
      document.getElementById('find_btn').click();
      return false;
    }
    return true;
}
  
//---------------------------------------------------------------------
function date_to_ddmmyyyy(date) {
    // Used to convert to eTapestry date format

    if(!date)
      return;
  
    var day = date.getDate();
    if(day < 10)
      day = '0' + String(day);
  
    var month = date.getMonth() + 1;
    if(month < 10)
      month = '0' + String(month);
  
    return day + '/' + month + '/' + String(date.getFullYear());
}

//------------------------------------------------------------------------------
function buildAdminPanel() {
    // dev_mode pane buttons
    $('#admin_pane').hide();
    $('#dev_pane').show();

    update_maps_btn = addAdminPanelBtn(
      'dev_pane',
      'update_maps_btn',
      'Update Maps',
      'btn-outline-primary');

    update_maps_btn.click(function() {
        $.ajax({
          type: 'POST',
          url: $URL_ROOT + 'booker/update_maps',
          data: {},
          dataType: 'json'
        })
        .done(function(response) {
            console.log(response);
            alertMsg('Updating maps...', 'info');
        });
    });

    print_maps_btn = addAdminPanelBtn(
      'dev_pane',
      'print_maps_btn',
      'Print Maps',
      'btn-outline-primary');

		// Prints Routific job_id to console
    print_maps_btn.click(function() {
        $.ajax({
          type: 'POST',
          url: $URL_ROOT + 'booker/get_maps',
          data: {},
          dataType: 'json'
        })
        .done(function(response) {
            console.log(response);
            alertMsg('Map data printed to console.', 'success')
        });
    });
}
