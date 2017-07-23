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
        'accounts/get/location',
        data={'acct_id':acct_id},
        function(response) {
            var data = response['data'];
            console.log(data);
            initGoogleMap(data['geometry']['location'], 12, map_style);
            addMarker("Home", data['geometry']['location'], HOME_ICON);
        });

    api_call(
        'accounts/get',
        data={'acct_id':acct_id},
        function(response) {
            acct = response['data'];
            displayAcctData(acct);
        
            // Need acct first to get ref for querying gift history
            api_call(
                'accounts/summary_stats',
                data={'ref':acct['ref']},
                displayDonationData);
        }
    );
}

//------------------------------------------------------------------------------
function displayDonationData(response) {
    /*Draw morris.js bar graph. 
    @gifts: list of simpliedifed eTapestry Gift objects w/ fields 'amount',
    'date', where 'date':{'$date':TIMESTAMP}. Sorted by descending date.
    */

    //console.log(response['data']);
    var gifts = response['data'];

    // Analyze gift stats, build chart data

    var n_gifts = gifts.length;
    var total = 0;
    var chart_data = [];

    for(var i=gifts.length-1; i>=0; i--) {
        // to date format: yyyy-mm-dd
        chart_data.push({
            'date': new Date(gifts[i]['date']['$date']).strftime('%Y-%m-%d'),
            'value': gifts[i]['amount'],
            'count': gifts[i]['amount']
        });

        if(gifts[i]['amount'] > 0)
            total += gifts[i]['amount'];
        else
            n_gifts--;
    }

    total = total.toFixed(2);

    if(n_gifts > 0)
        var avg_gift = (total/n_gifts).toFixed(2);
    else
        var avg_gift = "--";

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
function displayAcctData(acct) {

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
    $('#acct_id').html("#"+acct['id']);

    var contact_fields = ['name', 'address', 'city', 'state', 'postalCode', 'email', 'phones'];
    var internal_fields = ['ref', 'id', 'primaryPersona', 'nameFormat'];

    // Contact Info fields

    for(var i=0; i<contact_fields.length; i++) {
        var field = contact_fields[i];

        if(!acct.hasOwnProperty(field))
            continue;
        else {
            appendField(field, acct[field], $contact);
        }
    }

    // Custom fields
    var custom_fields = [
        "Signup Date",
        "Dropoff Date",
        "Status",
        "Next Pickup Date",
        "Neighborhood",
        "Reason Joined",
        "Referrer",
        "Date Cancelled",
        "Driver Notes",
        "Office Notes",
        "Block"
    ];
    var ignore = [ 'Data Source', 'Beverage Container Customer' ];

    var multi_selects = {};
    var text_areas = [];

    for(var j=0; j<custom_fields.length; j++) {
        for(var i=0; i<acct['accountDefinedValues'].length; i++) {
            var field = acct['accountDefinedValues'][i];

            if(custom_fields[j] != field['fieldName'])
                continue;

            if(field['displayType'] == 2) {
                if(multi_selects.hasOwnProperty(field['fieldName']))
                    multi_selects[field['fieldName']].push(field);
                else
                    multi_selects[field['fieldName']] = [field];

                continue;
            }
            else if(field['displayType'] == 3) {
                text_areas.push(field);
                continue;
            }

            appendUDF(field, $custom);

            if(field['fieldName'] == "Status")
                $('#status').html(field['value']);

            if(field['fieldName'] == 'Signup Date') {
                var d_comps = field['value'].split('/');
                var date = new Date(d_comps[1]+'/'+d_comps[0]+'/'+d_comps[2]);
                $('#joined-d').html(date.strftime("%b %Y").toUpperCase());
            }
        }
    }

    for(var key in multi_selects) {
        var fields = multi_selects[key];
        var values = [];

        for(var i=0; i<fields.length; i++) {
            values.push(fields[i]['value']);
        }

        appendField(key, values.join(", "), $custom);
    }

    for(var i=0; i<text_areas.length; i++) {
        text_areas[i]['value'] = text_areas[i]['value'].trim();
        appendUDF(text_areas[i], $custom);
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
function appendUDF(field, $container) {

    var $lblDiv = $("<div class='pr-0 text-left'><label class='field align-top'></label></div>");
    var $valDiv = $("<div class='text-left'><label class='val align-top'></label></div>");

    // Text Area
    if(field['displayType'] == 3) {

        var $smallContainer = $("<div class='col-12 pt-3'></div>");
        $container.append($smallContainer);
        // @container now points to new sub-container
        $container = $smallContainer;

        $lblDiv.addClass('col-2').addClass('pl-0');
        $valDiv.addClass('col-12');
    }

    else {
        $lblDiv.addClass('col-2');
        $valDiv.addClass('col-4');
    }

    $lblDiv.find('label').html(field['fieldName']);

    var val = '';

    if(field['dataType'] == 1) { // Date
        var parts = field['value'].split('/');
        var date = new Date(parts[1]+'/'+parts[0]+'/'+parts[2]);
        val = date.strftime('%b %d, %Y');
    }
    else {
        if(field['value'])
            val = field['value'].replace(/\\n/g, '  ').replace(/\*/g, '');
    }

    $valDiv.find('label').html(val);

    $container.append($lblDiv).append($valDiv);
}

//------------------------------------------------------------------------------
function appendField(name, value, $element) {
    /*@field: str, int, or Phone object
    */

    if(!value)
        return;

    var fieldWidth = 2;
    var valWidth = 4;

    var div = "<DIV class='col-2 text-left'><label class='field align-top'>" + name.toTitleCase() + ": </label></div>";

    if(name == 'phones' && value) {
        for(var j=0; j<value.length; j++) {
            var phone = value[j];
            appendField(phone['type'], phone['number'], $contact);
        }
        return;
    }

    if(typeof value === 'object')
        div += 
            '<div class="text-left" style="">' + 
                JSON.stringify(value, null, 2).replace(/\\n/g, "<BR>") +
            '</div>' +
          '</DIV>';
    else if(typeof(value) == "string")
        div += "<div class='col-"+valWidth+"'><label class='val align-top'>" + value.replace(/\\n/g, "") + "</label></DIV>";
    else
        div += '<label class="val align-top">'+ value + '</label></DIV>';

    $element.append(div);
}


map_style = [
  {
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#f5f5f5"
      }
    ]
  },
  {
    "elementType": "labels.icon",
    "stylers": [
      {
        "visibility": "off"
      }
    ]
  },
  {
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#616161"
      }
    ]
  },
  {
    "elementType": "labels.text.stroke",
    "stylers": [
      {
        "color": "#f5f5f5"
      }
    ]
  },
  {
    "featureType": "administrative.land_parcel",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#bdbdbd"
      }
    ]
  },
  {
    "featureType": "poi",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#eeeeee"
      }
    ]
  },
  {
    "featureType": "poi",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#757575"
      }
    ]
  },
  {
    "featureType": "poi.park",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#e5e5e5"
      }
    ]
  },
  {
    "featureType": "poi.park",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#9e9e9e"
      }
    ]
  },
  {
    "featureType": "road",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#ffffff"
      }
    ]
  },
  {
    "featureType": "road.arterial",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#757575"
      }
    ]
  },
  {
    "featureType": "road.highway",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#dadada"
      }
    ]
  },
  {
    "featureType": "road.highway",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#616161"
      }
    ]
  },
  {
    "featureType": "road.local",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#9e9e9e"
      }
    ]
  },
  {
    "featureType": "transit.line",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#e5e5e5"
      }
    ]
  },
  {
    "featureType": "transit.station",
    "elementType": "geometry",
    "stylers": [
      {
        "color": "#eeeeee"
      }
    ]
  },
  {
    "featureType": "water",
    "elementType": "geometry",
    "stylers": [
      {
        //"color": "#c9c9c9"
        "color": "#cef2ff"
      }
    ]
  },
  {
    "featureType": "water",
    "elementType": "labels.text.fill",
    "stylers": [
      {
        "color": "#9e9e9e"
      }
    ]
  }
];
