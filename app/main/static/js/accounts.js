/* accounts.js */

acct = null;

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//---------------------------------------------------------------------
function accountsInit() {
    $( document ).ready(function() {
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });
    });
    $(window).on('resize', function(){
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });
    });

    if(location.href.indexOf('?') > -1) {
        var args = location.href.substring(location.href.indexOf('?')+1, location.length);
        getAcct(args.substring(args.indexOf('=')+1, args.length));
    }

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').prop('hidden', true);
    addSocketIOHandlers();
}

//------------------------------------------------------------------------------
function addSocketIOHandlers() {

    var socketio_url = 'https://' + document.domain + ':' + location.port;
    var socket = io.connect(socketio_url);
    socket.on('connect', function(data){
        console.log('Socket.IO connected.');
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
        
            // Need acct first to get ref for querying gift history
            api_call(
                'accounts/summary_stats',
                data={'ref':acct['ref']},
                drawGiftHistoryStats);
        }
    );
}

//------------------------------------------------------------------------------
function drawGiftHistoryStats(response) {
    /*Draw morris.js bar graph. 
    @gifts: list of simpliedifed eTapestry Gift objects w/ fields 'amount',
    'date', where 'date':{'$date':TIMESTAMP}. Sorted by descending date.
    */

    console.log(response['data']);
    var gifts = response['data'];

    // Analyze gift stats, build chart data

    var n_gifts = gifts.length;
    var total = 0;
    var chart_data = [];

    for(var i=n_gifts-1; i>=0; i--) {
        // to date format: yyyy-mm-dd
        chart_data.push({
            'date': new Date(gifts[i]['date']['$date']).strftime('%Y-%m-%d'),
            'value': gifts[i]['amount'],
            'count': gifts[i]['amount']
        });

        total += gifts[i]['amount'];
    }

    total = total.toFixed(2);
    var avg_gift = (total/n_gifts).toFixed(2);

    // Render summary info



    $('#n_gifts').html(n_gifts);
    $('#n_gifts').parent().prop('hidden', false);

    $('#avg label').html('$'+ avg_gift.split(".")[0] +'.');
    $('#avg span').html( avg_gift.split(".")[1]);
    $('#avg').parent().prop('hidden', false);

    $('#total label').html('$' + total.split(".")[0] + '.');
    $('#total span').html( total.split(".")[1]);
    $('#total').parent().prop('hidden', false);

    $('.showcase .spinner').hide();
    $('.showcase .content').show();

    $('#chart-load').hide();
    $('#don_chart').prop('hidden',false);
    drawMorrisChart('don_chart', chart_data, 'date', ['value']);

    $('#last-gave-d').html(new Date(gifts[0]['date']['$date']).strftime('%b %Y').toUpperCase());
    $('#timeline').prop('hidden',false);
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
    $('#action_panel').prop('hidden',false);

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

            if(field['fieldName'] == 'Signup Date') {
                var d_comps = field['value'].split('/');
                var date = new Date(d_comps[1]+'/'+d_comps[0]+'/'+d_comps[2]);
                $('#joined-d').html(date.strftime("%b %Y").toUpperCase());
            }
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


