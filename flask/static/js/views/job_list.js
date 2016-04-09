function init() {
  addBravoTooltip();
  
  // Init socket.io
  var socketio_url = 'http://' + document.domain + ':' + location.port;

  console.log('attempting socket.io connection to ' + socketio_url + '...');

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

    $('#status-banner').text(msg);
    $('#status-banner').clearQueue();
    $('#status-banner').fadeIn('slow');
    $('#status-banner').delay(10000);
    $('#status-banner').fadeOut(3000);

    $status_td = $job_row.find('[name="job-status"]');

    if (data['status'] == "completed")
        $status_td.css({'color':'green'}); // FIXME: Breaks Bootstrap style
    else if(data['status'] == "in-progress")
        $status_td.css({'color':'red'}); // FIXME: Breaks Bootstrap style
      
    $status_td.text(data['status'].toTitleCase());
    //$('.delete-btn').hide();
  });

  if(location.href.indexOf('?msg=') > -1) {
      var uri = decodeURIComponent(location.href);
      var ind = uri.indexOf('?msg=');
      var msg = uri.substring(ind+5, uri.length);
      $('#status-banner').text(msg);
  }

  if($('#status-banner').text()) {
      $('#status-banner').fadeIn('slow');
      $('#status-banner').delay(10000);
      $('#status-banner').fadeOut(3000);
  }

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
      var job_uuid = $tr.attr('id');

      console.log('prompt to delete job_id: ' + job_uuid);

      $('.modal-title').text('Confirm');
      $('.modal-body').text('Really delete this job?');
      $('#btn-secondary').text('No');
      $('#btn-primary').text('Yes');

      $('#btn-primary').click(function() {
          var request =  $.ajax({
              type: 'GET',
              url: $URL_ROOT + 'reminders/'+job_uuid+'/cancel'
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

  console.log(n);
  console.log(num_page_records);

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

  $('body').css('display','block');
}
