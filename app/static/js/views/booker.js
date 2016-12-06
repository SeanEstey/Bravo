
//---------------------------------------------------------------------
function booker_init() {
    alertMsg(
      'Enter an <b>account ID</b>, <b>address</b>, or <b>postal code</b> below',
      'info', 
      -1
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
function search(form) {  
    var search_value = form.elements['search_box'].value;
    
    form.elements['search_box'].value = '';
    
    if(!search_value) {
      return false;
    }

    console.log('Starting search for: ' + search_value);

    fadeAlert();
    clearSearchResults(false);

    $('#results').show();
    $('#results tr:first').hide();

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

    $('#results tr:first').show();

    alertMsg(response['description'], 'success', -1);

    for(var i=0; i<response['results'].length; i++) {
        var result = response['results'][i];
        var $row = 
          '<tr style="background-color:white">' + 
            '<td name="date">' + 
              new Date(result['event']['start']['date']).strftime('%B %d %Y') + 
            '</td>' +
            '<td name="block">' + result['name'] + '</td>' +
            '<td>' + result['booked'] + '</td>' +
            '<td>' + '100' + '</td>' +
            '<td>' + result['distance'] + '</td>' +
            '<td name="postal">' + result['event']['location'] + '</td>' +
            '<td>' + result['area'] + '</td>' +
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
function clearSearchResults(hide) {
    $('#results tbody').html('');

    if(hide == true)
        $('#results').hide();
}

//---------------------------------------------------------------------
function showBookingModal(block, date, aid, name) {
    showModal(
      'mymodal',
      'Confirm Booking',
      $('#booking_options').html(),
      'Book',
      'Close'
    );

    $('#mymodal label[name="name"]').html('Account Name: <b>' + name + '</b>');
    $('#mymodal label[name="block"]').html('Block: <b>' + block + '</b>');
    $('#mymodal label[name="date"]').html(
        'Date: <b>' + new Date(date).strftime('%B %d %Y') + '</b>'
    );
    $('#mymodal textarea').val(
        new Date(date).strftime('%b %d') + ': Pickup requested.'
    );

    $('#mymodal .btn-primary').click(function() {
        requestBooking(
            aid,
            block, 
            new Date(date).strftime('%d/%m/%Y'),
            $('#mymodal').find('#driver_notes').val()
        );
    });
}
  
//---------------------------------------------------------------------
function requestBooking(aid, block, date, notes) {
    $('#mymodal').find('#booker-loader').show();
    $('#mymodal').find('.btn.loader').fadeTo('fast', 1);

		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'booker/book',
			data: {
        'block': block,
        'date': date,
        'aid': aid,
        'driver_notes': notes
      },
			dataType: 'json'
		})
		.done(function(response) {
        console.log(response);

        $('#booker-loader').fadeOut('fast');

        $('#mymodal').modal('hide');

        if(response['status'] == 'success') {
            alertMsg(response['description'], 'success');
            clearSearchResults(true);
        }
        else {
            alertMsg(response['description'], 'danger');
        }

        setTimeout(function(){
            alertMsg(
              'Enter an <b>account ID</b>, <b>address</b>, or <b>postal code</b> below',
              'info', 
              -1
            );
        }, 10000);
    });
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
