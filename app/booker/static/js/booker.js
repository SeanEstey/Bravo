/* booker.js */

gmaps = null;
map_data = {};
shapes = [];
markers = [];
current_map = null;

DEF_ZOOM = 11;
DEF_MAP_ZOOM = 14;
MAX_ZOOM = 21;
CALGARY = {lat:51.055336, lng:-114.077959};
MAP_FILL ='#99ccff';
MAP_STROKE = '#6666ff';

DEF_SEARCH_PROMPT = 'Enter an <b>account ID</b>, <b>address</b>, or <b>postal code</b> below';

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function bookerInit() {

    //alertMsg(DEF_SEARCH_PROMPT, 'info', -1);
    $('#search_ctnr').prepend($('.br-alert'));
    loadMapData();
    addSocketIOHandlers();
}

//------------------------------------------------------------------------------
function initGoogleMap() {

    gmaps = new google.maps.Map(
        $('#map')[0],
        {mapTypeId:'roadmap', center:CALGARY, zoom:DEF_ZOOM}
    );
    console.log('Google Map initialized.');
}

//------------------------------------------------------------------------------
function loadMapData() {

    api_call(
      'maps/get',
      data=null,
      function(response){
          if(response['status'] == 'success') {
              console.log('Map data loaded');
              map_data = response['data'];
          }
      }
    );
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {

    var socketio_url = 'https://' + document.domain + ':' + location.port;
    var socket = io.connect(socketio_url);
    socket.on('connect', function(data){
        console.log('Socket.IO connected.');
    });
    socket.on('update_maps', function(data) {
        console.log(data['description']);
        alertMsg(data['description'], 'success');
    });
}

//---------------------------------------------------------------------
function validateSearch(form) {
    var query = form.elements['search_box'].value;
    form.elements['search_box'].value = '';
    if(!query) {
      return false;
    }

    search(query);
}

//---------------------------------------------------------------------
function search(query, radius, weeks) {

    console.log(
      'submitting search: "' + query + '", radius: '+ radius +', weeks: '+ weeks);

    fadeAlert();
    clearSearchResults(false);

    $('#results2').show();
    $('#results2 tr:first').hide();

    $('#search-loader').slideToggle(function() {
        $('#search-loader .btn.loader').fadeTo('fast', 1);
    });

    $.ajax({
        type: 'POST',
        url: $URL_ROOT + 'api/booker/search',
        data: {
            'query':query,
            'radius': radius,
            'weeks': weeks},
        dataType: 'json'})
    .done(function(response) {
        console.log(response);

        if(response['status'] != 'success') {
            alertMsg(response['description'], 'danger', -1);

            $('#search-loader .btn.loader').fadeTo('fast', 0, function() {
                $('#search-loader').slideToggle();
            });
            return;
        }
        displaySearchResults(response['data']);
    })
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
function displaySearchResults(response) {

    $('#search-loader .btn.loader').fadeTo('slow', 0, function() {
        $('#search-loader').slideUp();
    });

    $('#results2 tr:first').show();

    alertMsg(response['description'], 'success', -1);

    // save prev query in banner in case user wants to expand search
    $('.br-alert').data('query', response['query']);
    $('.br-alert').data('radius', response['radius']);
    $('.br-alert').data('weeks', response['weeks']);

    for(var i=0; i<response['results'].length; i++) {
        var result = response['results'][i];
        
        // HACK: convert local date to UTC
        var local_date = new Date(
          new Date(result['event']['start']['date']).getTime() +
          7*60*60*1000
        );

        var $row = $(
          '<tr style="background-color:white">' + 
            '<td>'+
              '<div>'+
                '<label>'+
                  '<input name="radio-stacked" type="radio"><span></span>'+
                '</label>'+
              '</div>'+
            '</td>'+
            '<td name="date">' + 
              local_date.strftime('%B %d %Y') + 
            '</td>' +
            '<td name="block">' + result['name'] + '</td>' +
            '<td>' + result['booked'] + '</td>' +
            '<td>' + result['distance'] + '</td>' +
          '</tr>'
        );
        $row.find('input').click(selectResult);
        $('#results2 tbody').append($row);

        // save account info in button data
        if(response.hasOwnProperty('account')) {
            $('#results2 tr:last button').data('aid', response['account']['id']);
            $('#results2 tr:last button').data('name', response['account']['name']);
            $('#results2 tr:last button').data('email', response['account']['email']);
        }
    }

    $('#a_radius').off('click');
    $('#a_radius').click(function() {
        showExpandRadiusModal();
    });

    $('button[name="book_btn"]').off('click');
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
function selectResult() {

    $row = $(this).parent().parent().parent().parent();
    var this_block = $row.find('[name="block"]').text();
    console.log('this_block: ' +this_block);

    var match = false;
    var idx=0;

    while(!match && idx<map_data['features'].length) {
        var map = map_data['features'][idx];
        var title = map['properties']['name'];
        var block = parse_block(title);
        if(this_block == block) {
            match = true;
            break;
        }
        
        idx++;
    }

    var coords = map_data['features'][idx]['geometry']['coordinates'][0];
    drawMapPolygon(coords);
}

//------------------------------------------------------------------------------
function drawMapPolygon(coords) {

    var paths = [];
    for(var i=0; i<coords.length; i++) {
        paths.push({"lat":coords[i][1], "lng":coords[i][0]});
    }

    var shape = new google.maps.Polygon({
        paths: paths,
        strokeColor: MAP_STROKE,
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: MAP_FILL,
        fillOpacity: 0.35
    });
    shape.setMap(gmaps);
    //shapes.push(shape);

    //var center = centerPoint(coords);
    //gmaps.setCenter({'lat':center[1], 'lng':center[0]});
    //setOptimalZoom(paths);
}

//---------------------------------------------------------------------
function clearSearchResults(hide) {
    $('#results2 tbody').html('');

    if(hide == true)
        $('#results2').hide();
}

//---------------------------------------------------------------------
function showExpandRadiusModal() {
    var radius = Number($('.br-alert').data('radius'));

    showModal(
      'mymodal',
      'Confirm',
      'Do you want to expand the search radius from ' + radius.toPrecision(2) + 'km?',
      'Yes',
      'No');

    $('#mymodal .btn-primary').click(function() {
        $('#mymodal').modal('hide');
        search(
          $('.br-alert').data('query'),
          radius + 2.0
        );
    });
}

//---------------------------------------------------------------------
function showEnterIDModal(block, date) {
    showModal(
      'mymodal',
      'Confirm Booking',
      $('#booking_options').html(),
      'Next',
      'Close');

    $('#mymodal').find('#acct_info').hide();
    $('#mymodal').find('#enter_aid').show();

    $('#mymodal').on('shown.bs.modal', function () {
        $('#mymodal').find('#aid').focus();
    })

    $('#mymodal .btn-primary').click(function() {
        console.log('querying aid: ' + $('#mymodal input[id="aid"]').val());

        $.ajax({
            type: 'POST',
            url: $URL_ROOT + 'api/accounts/get',
            data: {
                'acct_id': $('#mymodal input[id="aid"]').val(),
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
            
            var acct = response['data']; //['account'];

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

    var date_obj = new Date(date);
    var today = new Date();

    if(date_obj.getMonth() == today.getMonth() &&  date_obj.getDate() == today.getDate()) {
        $('#mymodal #routed_warning').html(
            "<strong>Warning: </strong>" +
            block + ' has already been routed.<br> ' +
            'By booking this account, the route will also be updated.');
        $('#mymodal #routed_warning').show();
    }

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

    $('#mymodal .btn-primary').off('click');
    $('#mymodal .btn-primary').click(function() {
        $(this).prop('disabled', true);

        requestBooking(
          aid,
          block, 
          new Date(date).strftime('%d/%m/%Y'),
          $('#mymodal').find('#driver_notes').val(),
          name,
          email,
          $('#mymodal').find('input[id="send_email_cb"]').prop('checked'));
    });
}
  
//---------------------------------------------------------------------
function requestBooking(aid, block, date, notes, name, email, confirmation) {

    /*$('#mymodal').find('#booker-loader').slideToggle(function() {
        $('#mymodal').find('#booker-loader .btn.loader').fadeTo('fast', 1);
    });*/

    api_call(
        'booker/create',
        data={
            'block': block,
            'date': date,
            'aid': aid,
            'driver_notes': notes,
            'first_name': name,
            'email': email,
            'confirmation': confirmation
        },
        function(response){
            console.log(response);
            $('#mymodal .btn-primary').prop('disabled', false);
            //$('#booker-loader').fadeOut('fast');
            //$('#booker-loader').hide();
            $('#mymodal').modal('hide');

            if(response['status'] == 'success') {
                alertMsg(response['data'], 'success');
                clearSearchResults(true);
            }
            else
                alertMsg(response['data'], 'danger');

            setTimeout(function(){ alertMsg(DEF_SEARCH_PROMPT, 'info',-1);}, 10000);
        }
    );
}
