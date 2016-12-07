
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
            $('#results tr:last button').data('email', response['account']['email']);
        }
    }

    $('button[name="book_btn"]').click(function() {
				$tr = $(this).parent().parent();

				if(!$(this).data('aid')) {
						showEnterIDModal(
								$tr.find('[name="block"]').text(),
								$tr.find('[name="date"]').text());
				}
				else {
						showConfirmModal(
							$tr.find('[name="block"]').text(),
							$tr.find('[name="date"]').text(),
							$tr.find('button').data('aid'),
							$tr.find('button').data('name'),
							$tr.find('button').data('email'));
				}
    });
}

//---------------------------------------------------------------------
function clearSearchResults(hide) {
    $('#results tbody').html('');

    if(hide == true)
        $('#results').hide();
}


//---------------------------------------------------------------------
function showEnterIDModal(block, date) {
		showModal(
			'mymodal',
			'Confirm Booking',
			$('#booking_options').html(),
			'Next',
			'Close'
		);

		$('#mymodal').find('#acct_info').hide();
		$('#mymodal').find('#enter_aid').show();

    $('#mymodal .btn-primary').click(function() {
				console.log('querying aid: ' + $('#mymodal input[id="aid"]').val());

				$.ajax({
					type: 'POST',
					url: $URL_ROOT + 'booker/get_acct',
					data: {
						'aid': $('#mymodal input[id="aid"]').val(),
					},
					dataType: 'json'
				})
				.done(function(response) {
						console.log(response);

						if(response['status'] != "success") {
								$('#mymodal').modal('hide');
								alertMsg(response['description'], 'danger');
								return false;
						}

						$('#mymodal').find('#acct_info').show();
						$('#mymodal').find('#enter_aid').hide();
						
						var acct = response['account'];

						showConfirmModal(
								block,
								date,
								acct['id'],
								acct['name'],
								acct['email']
						);
				});
    });
}

//---------------------------------------------------------------------
function showConfirmModal(block, date, aid, name, email) {
		showModal(
			'mymodal',
			'Confirm Booking',
			$('#booking_options').html(),
			'Book',
			'Close'
		);

		if(!email) {
				email = 'None';
				$('#mymodal').find('input[id="send_email_cb"]').prop('disabled',true);
				$('#mymodal').find('input[id="send_email_cb"]').attr('checked',false);
				$('#mymodal').find('.form-check-label').css('color', '#ced3db');
		}

    $('#mymodal label[name="name"]').html('Account Name: <b>' + name + '</b>');
    $('#mymodal label[name="email"]').html('Email: <b>' + email + '</b>');
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
            $('#mymodal').find('#driver_notes').val(),
						name,
						email,
						$('#mymodal').find('input[id="send_email_cb"]').prop('checked')
        );
    });
}
  
//---------------------------------------------------------------------
function requestBooking(aid, block, date, notes, name, email, confirmation) {
    $('#mymodal').find('#booker-loader').slideToggle(function() {
        $('#mymodal').find('#booker-loader .btn.loader').fadeTo('fast', 1);
    });

		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'booker/book',
			data: {
        'block': block,
        'date': date,
        'aid': aid,
        'driver_notes': notes,
				'name': name,
				'email': email,
				'confirmation': confirmation
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
