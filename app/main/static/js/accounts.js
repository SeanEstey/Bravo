/* accounts.js */

acct = null;

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function accountsInit() {

    alertMsg('Enter search terms below', 'info', -1);

    $('#search_ctnr').prepend($('.br-alert'));
    addSocketIOHandlers();

    $('#find_acct').click(function() {
       var acct_id = $('#acct_input').val();
       getAcct(acct_id);
       //getBookOptions(acct_id);
    });

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
function getAcct(acct_id) {

    api_call(
        'accounts/get',
        data={'acct_id':acct_id},
        function(response) {
            acct = response['data'];
            console.log(acct);
            display(acct);
        });
}

//---------------------------------------------------------------------
function display(acct) {

    var ignore = [
        'userRoleRef', 'donorRoleRef', 'envelopeSalutation', 'shortSalutation',
        'longSalutation', 'primaryPersona', 'country', 'firstName', 'lastName', 'name'
    ];

    // Simple fields
    for(var k in acct) {
        if(typeof(acct[k]) != "object" && ignore.indexOf(k) == -1)
            appendField(k, acct[k]);
    }

    for(var i=0; i<acct['phones'].length; i++) {
        var phone = acct['phones'][i];
        appendField(phone['type'], phone['number']);
    }

    for(var i=0; i<acct['accountDefinedValues'].length; i++) {
        var udf = acct['accountDefinedValues'][i];
        appendField(udf['fieldName'], udf['value']);
    }

    $('#acct_name').html(acct['name']);
    
}

//------------------------------------------------------------------------------
function appendField(field, value) {

    if(!value)
        return;

    var div = "<DIV class='text-left'><B>" + field + "</B>: ";

    if(typeof value === 'object')
        div += 
            '<div class="text-left" style="">' + 
                JSON.stringify(value, null, 2).replace(/\\n/g, "<BR>") +
            '</div>' +
          '</DIV>';
    else
        div += value + '</DIV>';

    $('#properties').append(div);
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
function clearSearchResults(hide) {
    $('#results2 tbody').html('');

    if(hide == true)
        $('#results2').hide();
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
