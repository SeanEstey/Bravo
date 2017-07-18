/* accounts.js */

acct = null;

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function accountsInit() {

    alertMsg('Enter search terms below', 'info', -1);

    if(location.href.indexOf('?') > -1) {
        var args = location.href.substring(location.href.indexOf('?')+1, location.length);
        getAcct(args.substring(args.indexOf('=')+1, args.length));
    }

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').prop('hidden', true);
    addSocketIOHandlers();

    $('#find_acct').click(function() {
       var acct_id = $('#acct_input').val();
       getAcct(acct_id);
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

            api_call(
                'accounts/summary_stats',
                data={'ref':acct['ref']},
                function(response) {
                    console.log(response['data']);
                    var data = response['data'];
                    $('#avg').html('$'+data['average'].toFixed(2));
                    $('#total').html('$'+data['total'].toFixed(2));
                    $('#n_gifts').html(data['n_gifts']+ ' Gifts');
                });
        });
}

//---------------------------------------------------------------------
function display(acct) {

    $contact = $('#contact .row');
    $contact.empty();
    $custom = $('#custom .row');
    $custom.empty();
    $internal = $('#internal .row');
    $internal.empty();

    $summary = $('#sum_panel');
    $summary.prop('hidden',false);
    $('#contact_panel').prop('hidden',false);
    $('#custom_panel').prop('hidden',false);

    $('#acct_name').html(acct['name']);


    var contact_fields = ['name', 'address', 'city', 'state', 'postalCode', 'email', 'phones'];
    var internal_fields = ['ref', 'id', 'primaryPersona', 'nameFormat'];

    // Contact Info fields

    for(var i=0; i<contact_fields.length; i++) {
        var field = contact_fields[i];

        if(!acct.hasOwnProperty(field))
            continue;

        if(field == 'phones' && acct['phones']) {
            for(var j=0; j<acct['phones'].length; j++) {
                var phone = acct['phones'][j];
                appendField(phone['type'], phone['number'], $contact);
            }
        }
        else {
            appendField(field.toTitleCase(), acct[field], $contact);
        }
    }

    // Custom fields
    var custom_fields = [
        "Signup Date",
        "Dropoff Date",
        "Status",
        "Next Pickup Date",
        "Neighborhood",
        "Block",
        "Reason Joined",
        "Referrer",
        "Date Cancelled",
        "Driver Notes",
        "Office Notes"
    ];
    var ignore = [ 'Data Source', 'Beverage Container Customer' ];

    for(var j=0; j<custom_fields.length; j++) {
        for(var i=0; i<acct['accountDefinedValues'].length; i++) {
            var field = acct['accountDefinedValues'][i];

            if(custom_fields[j] != field['fieldName'])
                continue;

            appendField(field['fieldName'], field['value'], $custom);

            if(field['fieldName'] == "Status")
                $('#status').html(field['value']);
        }
    }

    // Internal fields
    for(var i=0; i<internal_fields.length; i++) {
        var field = internal_fields[i];

        if(field.indexOf('Date') > -1) {
            if(acct[field]) {
                var date = new Date(acct[field]['$date']).strftime('%b %d, %Y @ %H:%M');
            }
            else
                var date = 'None';
            appendField(field, date, $internal);
        }
        else {
            appendField(field, acct[field], $internal);
        }
    }

    var date = new Date(acct['personaCreatedDate']['$date']);
    $('#personaCreatedDate').html(
        date.strftime('%b %d, %Y ') + '<i class="fa fa-clock-o"></i>' + date.strftime(' %I:%M %p'));

    if(acct['personaLastModifiedDate']) {
        var date = new Date(acct['personaLastModifiedDate']['$date']);
        $('#personaLastModifiedDate').html(
            date.strftime("%b %d, %Y ") + '<i class="fa fa-clock-o"></i>' + date.strftime(" %I:%M %p"));
    }

    var date = new Date(acct['personaCreatedDate']['$date']);
    $('#accountCreatedDate').html(date.strftime('%b %d, %Y ') + '<i class="fa fa-clock-o"></i>' + date.strftime(' %I:%M %p'));

    if(acct['accountLastModifiedDate']) {
        var date = new Date(acct['accountLastModifiedDate']['$date']);
        $('#accountLastModifiedDate').html(
            date.strftime("%b %d, %Y ") + '<i class="fa fa-clock-o"></i>' + date.strftime(" %I:%M %p"));
    }

}

//------------------------------------------------------------------------------
function appendField(field, value, $element) {

    if(!value)
        return;

    var div = "<DIV class='col-6 text-left'><label class='field align-top'>" + field + "</label>: ";

    if(typeof value === 'object')
        div += 
            '<div class="text-left" style="">' + 
                JSON.stringify(value, null, 2).replace(/\\n/g, "<BR>") +
            '</div>' +
          '</DIV>';
    else if(typeof(value) == "string")
        div += '<label class="val align-top">' + value.replace(/\\n/g, "") + '</label></DIV>';
    else
        div += '<label class="val align-top">'+ value + '</label></DIV>';

    $element.append(div);
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
