
function init() {
	loadTooltip();
	buildAdminPanel();
	addDeleteBtnHandlers();
	addSocketIOHandlers();
	addPageNavHandlers();
	showAdminServerStatus();
	console.log('all js loaded');
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
/*
    $('.delete-btn').button({
        icons: {
          primary: 'ui-icon ui-icon-trash'
        },
        text: false
    })*/

    $('.delete-btn').each(function(){ 
      $(this).click(function(){
        var $tr = $(this).parent().parent();
        var event_uuid = $tr.attr('id');

        console.log('prompt to delete job_id: ' + event_uuid);

        $('.modal-title').text('Confirm');
				$('.modal-body').html('');
        $('.modal-body').text('Really delete this job?');
        $('#btn-secondary').text('No');
        $('#btn-primary').text('Yes');

        $('#btn-primary').click(function() {
            var request =  $.ajax({
                type: 'GET',
                url: $URL_ROOT + 'notify/'+event_uuid+'/cancel'
            });

            request.done(function(msg){
                if(msg == 'OK')
                  $tr.remove();
            });
            $('#mymodal').modal('hide'); 
        });

        $('#mymodal').modal('show');
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

    socket.on('update_job', function(data) {
      // data format: {'id': id, 'status': status}
      if(typeof data == 'string')
          data = JSON.parse(data);

      console.log('received update: ' + JSON.stringify(data));

      $job_row = $('#'+data['id']);

      if(!$job_row)
          return console.log('Could not find row with id=' + data['id']);
     
      var job_name = $job_row.find('[name="job-name"]').text(); 
      var msg = 'Job \''+job_name+'\' ' + data['status'];

      alertMsg(msg, 'error', 10000);

      $status_td = $job_row.find('[name="job-status"]');

      if (data['status'] == "completed")
          $status_td.css({'color':'green'}); // FIXME: Breaks Bootstrap style
      else if(data['status'] == "in-progress")
          $status_td.css({'color':'red'}); // FIXME: Breaks Bootstrap style
        
      $status_td.text(data['status'].toTitleCase());
      //$('.delete-btn').hide();
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
   
    // Add admin_mode pane buttons
		$('#admin_pane').hide();

		addAdminPanelBtn(
			'dev_pane',
			'schedule-btn',
			'Schedule Block'
		).click(function() {
        $('.modal-title').text('Schedule Block');
				var form = "<form id='myform' method=post>" +
					"<input width='100%' id='block' class='input' name='block' type='text'></input>" +
					"</form>";
				$('.modal-body').html(form);
        $('#btn-secondary').text('Cancel');
        $('#btn-primary').text('Schedule');
				$('#mymodal').modal();

        $('#btn-primary').click(function() {
            $('#mymodal').modal('hide'); 

						var block = $('#block').val();
						$('.modal-body').html('');

						$.ajax({
							context: this,
							type: 'POST',
							url: $URL_ROOT + 'notify/'+block+'/schedule'
						})
						.done(
							function(response) {
                alertMsg('Response: ' + response['description'], 'success');
								// write a view func for pickup_service.create_reminder_event(agency_conf['name'], block, _date)
							}
						);
				});
		});


}
