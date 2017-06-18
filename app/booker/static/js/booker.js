/* booker.js */

gmaps = null;
map_data = {};
acct = null;
current_polygon = null;
current_marker = null;

DEF_ZOOM = 11;
DEF_MAP_ZOOM = 14;
MAX_ZOOM = 21;
CALGARY = {lat:51.055336, lng:-114.077959};
MAP_FILL ='#99ccff';
MAP_STROKE = '#6666ff';

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function bookerInit() {

    alertMsg('Enter search terms below', 'info', -1);

    $('#search_ctnr').prepend($('.br-alert'));
    loadMapData();
    addSocketIOHandlers();

    $('#find_acct').click(function() {
       searchAcct($('#acct_input').val());
    });

    $('#find_block').click(function() {
       search($('#block_input').val());
    });

    $('#book_btn').click(showConfirmModal);
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
function searchAcct(acct_id) {
    
    search(acct_id);

    api_call(
        'booker/get_acct_geo',
        data={'acct_id': acct_id},
        function(response){
            console.log(response['status']);
            console.log(response['data']['acct']);
            acct = response['data']['acct'];
            var title = response['data']['acct']['name'];
            var coords = response['data']['coords'];
            addMarker(title, coords);
        });
}

//---------------------------------------------------------------------
function search(query, radius, weeks) {

    console.log(
      'submitting search: "' + query + '", radius: '+ radius +', weeks: '+ weeks);

    fadeAlert();
    clearSearchResults(false);

    $('#results2').show();
    $('#results2 tr:first').hide();

    alertMsg('Searching...', 'info');

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

    var MAX_RESULTS = 9;

    $('#results2').prop('hidden', false);
    $('#results2 tr:first').show();

    alertMsg(response['description'], 'success', -1);

    // save prev query in banner in case user wants to expand search
    $('.br-alert').data('query', response['query']);
    $('.br-alert').data('radius', response['radius']);
    $('.br-alert').data('weeks', response['weeks']);

    for(var i=0; i<response['results'].length; i++) {
        if(i > MAX_RESULTS)
            break;

        var result = response['results'][i];
        
        // HACK: convert local date to UTC
        var local_date = new Date(
          new Date(result['event']['start']['date']).getTime() +
          7*60*60*1000
        );

        var $row = $(
          '<tr style="background-color:white">' + 
            '<td style="width:8%">'+
              '<div>'+
                '<label>'+
                  '<input name="radio-stacked" type="radio"><span></span>'+
                '</label>'+
              '</div>'+
            '</td>'+
            '<td name="date" style="width:40%">' + 
              local_date.strftime('%b %d %Y') + 
            '</td>' +
            '<td name="block">' + result['name'] + '</td>' +
            //'<td>' + result['booked'] + '</td>' +
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

    var $row = $(this).closest('tr');
    var this_block = $row.find('[name="block"]').text();
    $('#block_input').val(this_block);

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

//---------------------------------------------------------------------    
function centerPoint(arr){
  /* Returns [x,y] coordinates of center of polygon passed in */
  
    var minX, maxX, minY, maxY;
    for(var i=0; i< arr.length; i++){
        minX = (arr[i][0] < minX || minX == null) ? arr[i][0] : minX;
        maxX = (arr[i][0] > maxX || maxX == null) ? arr[i][0] : maxX;
        minY = (arr[i][1] < minY || minY == null) ? arr[i][1] : minY;
        maxY = (arr[i][1] > maxY || maxY == null) ? arr[i][1] : maxY;
    }
    return [(minX + maxX) /2, (minY + maxY) /2];
}

//------------------------------------------------------------------------------
function drawMapPolygon(coords) {

    var paths = [];
    for(var i=0; i<coords.length; i++) {
        paths.push({"lat":coords[i][1], "lng":coords[i][0]});
    }

    if(current_polygon)
        current_polygon.setMap(null);

    current_polygon = new google.maps.Polygon({
        paths: paths,
        strokeColor: MAP_STROKE,
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: MAP_FILL,
        fillOpacity: 0.35
    });

    current_polygon.setMap(gmaps);

    var _coords = coords.slice();

    if(current_marker){
        var marker_coords = JSON.parse(JSON.stringify(current_marker.getPosition()));
        paths.push(marker_coords);
        _coords.push([marker_coords['lng'],marker_coords['lat'],0]);
    }

    var center = centerPoint(_coords);
    gmaps.setCenter({'lat':center[1], 'lng':center[0]});
    setOptimalZoom(paths);
}

//---------------------------------------------------------------------    
function addMarker(title, coords) {

    if(current_marker)
        current_marker.setMap(null);

    current_marker = new google.maps.Marker({
        position: coords,
        map: gmaps,
        title: title
    });
}

//------------------------------------------------------------------------------
function setOptimalZoom(paths) {

    var zoom = DEF_MAP_ZOOM;
    gmaps.setZoom(zoom);
    var bounds = gmaps.getBounds();

    if(inBounds(bounds, paths)) {
        while(inBounds(gmaps.getBounds(), paths) && zoom <= MAX_ZOOM) {
            gmaps.setZoom(++zoom);
        }

        // Zoom back out one level
        gmaps.setZoom(--zoom);
    }
    else {
        while(!inBounds(gmaps.getBounds(), paths)) {
            gmaps.setZoom(--zoom);
        }
    }

    console.log('Optimal zoom set to ' + zoom);
}

//------------------------------------------------------------------------------
function inBounds(bounds, paths) {

    for(var i=0; i<paths.length; i++) {
        if(!bounds.contains(paths[i]))
            return false;
    }

    return true;
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
function showConfirmModal() {

    showModal(
        'mymodal',
        'Confirm Booking',
        $('#booking_options').html(),
        'Book',
        'Close'
    );

    var $row = $('table input:checked').closest('tr');

    var date = new Date($row.find('td[name="date"]').text());
    var block = $('#block_input').val();

    var today = new Date();

    if(date.getMonth() == today.getMonth() &&  date.getDate() == today.getDate()) {
        $('#mymodal #routed_warning').html(
            "<strong>Warning: </strong>" +
            block + ' has already been routed.<br> ' +
            'By booking this account, the route will also be updated.');
        $('#mymodal #routed_warning').show();
    }

    if(!acct['email']) {
        $('#mymodal').find('input[id="send_email_cb"]').prop('disabled',true);
        $('#mymodal').find('input[id="send_email_cb"]').attr('checked',false);
        $('#mymodal').find('.form-check-label').css('color', '#ced3db');
    }

    $('#mymodal label[name="name"]').html('Account Name: <b>' + acct['name'] + '</b>');
    $('#mymodal label[name="email"]').html('Email: <b>' + acct['email'] + '</b>');
    $('#mymodal label[name="block"]').html('Block: <b>' + $('#block_input').val() + '</b>');
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
          acct['id'],
          block, 
          new Date(date).strftime('%d/%m/%Y'),
          $('#mymodal').find('#driver_notes').val(),
          acct['name'],
          acct['email'],
          $('#mymodal').find('input[id="send_email_cb"]').prop('checked'));
    });
}
  
//---------------------------------------------------------------------
function requestBooking(aid, block, date, notes, name, email, confirmation) {

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
            $('#mymodal').modal('hide');

            if(response['status'] == 'success') {
                alertMsg(response['data'], 'success');
                clearSearchResults(true);
            }
            else
                alertMsg(response['data'], 'danger');
        }
    );
}
