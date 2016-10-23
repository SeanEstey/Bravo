

//------------------------------------------------------------------------------
function init() {
    loadTooltip();
    buildAdminPanel();
    addDeleteBtnHandlers();
    addSocketIOHandlers();
    addPageNavHandlers();
		showBannerMsg();
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
    $('.delete-btn').button({
        icons: {
          primary: 'ui-icon-trash'
        },
        text: false
    })

    $('.delete-btn').addClass('redButton');

    $('.delete-btn').each(function(){ 
      $(this).click(function(){
        var $tr = $(this).parent().parent();
        var event_uuid = $tr.attr('id');

        console.log('prompt to delete job_id: ' + event_uuid);

        $('.modal-title').text('Confirm');
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

      bannerMsg(msg, 'error', 10000);

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
function showBannerMsg() {
    /*
    msg = ''
    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        msg += 'Sandbox mode. Etapestry: <b>read-only</b>. '\
               'Twilio: <b>simulation only</b>. Mailgun: <b>forwarding all</b>. '
    user = db['users'].find_one({'user': current_user.username})
    if user['admin']:
        msg += 'You have admin priviledges.'
    */
		
    $.ajax({
			type: 'POST',
			context: this,
			url: $URL_ROOT + 'notify/get_op_stats'
		})
		.done(function(response) {
				console.log('got server op stats');

				var msg = 'Hi ' + response['USER_NAME'] + ' ';

				if(response['TEST_SERVER'])
						msg += 'You are on Bravo Test server. ';
				else
						msg += 'You are on Bravo Live server. ';
				if(response['SANDBOX_MODE'])
						msg += 'Running in <b>sandbox mode</b> with ';
				if(response['CELERY_BEAT'])
						msg += '<b>scheduler enabled</b>. ';
				else
						msg += '<b>scheduler disabled</b>. ';

				if(response['ADMIN'])
						msg += 'You have admin priviledges. ';

				if(response['DEVELOPER'])
						msg += 'You have dev priviledges.';

				bannerMsg(msg, 'info', 15000);
		});
}

//------------------------------------------------------------------------------
function buildAdminPanel() {
   
    // Add admin_mode pane buttons

    // Add btns to fire each event trigger. trig_ids are stored in data-container 
    // "Status" columns i.e. "Voice SMS Status"
    $('th[id] a:contains("Status")').parent().each(function() {
        console.log('adding fire btn for trig_id ' + $(this).attr('id'));

        var col_caption = $(this).children().text();

        if(col_caption.search("Email") > -1) {
          var btn_caption = 'Send Emails Now';
          var btn_id = 'fire-voice-sms-btn';
        }
        else if(col_caption.search("Voice") > -1) {
          var btn_caption = 'Send Voice/SMS Now';
          var btn_id = 'fire-voice-sms-btn';
        }

        btn = addAdminPanelBtn(
          'admin_pane',
          btn_id,
          btn_caption,
          'btn-info', {
            'trig_id':$(this).attr('id')
          }
        );

        btn.click(function() {
            $.ajax({
              context: this,
              type: 'POST',
              url: $URL_ROOT + 'notify/' + $(this).data('trig_id') + '/fire'
            })
            .done(
              function(response, textStatus, jqXHR) {
                  response = JSON.parse(response);

                  console.log('request status: %s', response['status']);

                  if(response['status'] == 'OK') {
                      bannerMsg('Request authorized. Sending notifications...',
                                'info');

                      $(this).addClass('btn btn-primary disabled');
                  }
              }
            );
        });
    });

    stop_btn = addAdminPanelBtn(
      'admin_pane',
      'stop_btn',
      'Stop All',
      'btn-danger');
    
    // Add dev_mode admin pane buttons

    var args =  window.location.pathname.split('/');
    var evnt_id = args.slice(-1)[0];

    reset_btn = addAdminPanelBtn(
      'dev_pane',
      'reset_btn',
      'Reset All');

    reset_btn.click(function() {
      $.ajax({
				type: 'GET',
				url: $URL_ROOT + 'notify/' + evnt_id + '/reset'
			})
			.done(function(response, textStatus, jqXHR) {
				window.location.reload();
			});
    });

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Show Debug Info',
      'btn-info');

    show_debug_info_btn.click(function() {
        console.log('not implemented yet');
    });
}
