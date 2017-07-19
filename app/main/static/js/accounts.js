/* accounts.js */

acct = null;
dropdown = false;
dd_matches = [];

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function accountsInit() {

    alertMsg('Enter search terms below', 'info', -1);

    $('.dropdown-menu').width($('#acct_input').width());

    if(location.href.indexOf('?') > -1) {
        var args = location.href.substring(location.href.indexOf('?')+1, location.length);
        getAcct(args.substring(args.indexOf('=')+1, args.length));
    }

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').prop('hidden', true);
    addSocketIOHandlers();

    $('#acct_input').keypress(function (e) {
        if (e.which == 13) {
            console.log('Submitting search for "'+$(this).val()+'"');
            getAcct($(this).val());
            return false;
        }
    });

    $('#acct_input').keyup(function(e){
        showAutocompleteMatches($(this).val());
    });

    $('#find_acct').click(function() {
       var acct_id = $('#acct_input').val();
       getAcct(acct_id);
    });

}

//------------------------------------------------------------------------------
function showAutocompleteMatches(query) {
    
    $input = $('#acct_input');

    if(dropdown==false) {
        dropdown=true;
        $('#acct_input').trigger('click');
    }

    api_call(
        'accounts/get/autocomplete',
        data={'query':query},
        function(response) {

            dd_matches = response['data'];

            if(!Array.isArray(dd_matches)) {
                console.log('No results returned');
                return;
            }
            if(Array.isArray(dd_matches) && dd_matches.length == 0) {
                console.log('Zero results');
                return;
            }

            console.log('Found ' + dd_matches.length + ' matches.');

            $('.dropdown-menu').empty();

            for(var i=0; i<dd_matches.length; i++) {
                var account = dd_matches[i]['account'];

                var $a = $('<a class="dropdown-item" id="'+i+'" href="#">'+account['name']+'</a>');

                $a.click(function() {
                    var idx = Number($(this).prop('id'));
                    var account = dd_matches[idx]['account'];
                    console.log('Displaying Acct id='+account['id']);

                    display(account);

                    api_call(
                        'accounts/summary_stats',
                        data={'ref':account['ref']},
                        function(response) {
                            console.log(response['data']);
                            var data = response['data'];
                            $('#avg').html('$'+data['average'].toFixed(2));
                            $('#total').html('$'+data['total'].toFixed(2));
                            $('#n_gifts').html(data['n_gifts']+ ' Gifts');
                        });
                });

                $('.dropdown-menu').append($a);
            }
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
    $('#internal_panel').prop('hidden',false);

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
