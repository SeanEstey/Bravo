/* accounts.js */

gAcctId = null;
gAcct = null;
gGeolocation = null;
gMobile = null;

//---------------------------------------------------------------------
function accountsInit() {

    $(document).ready(function() {
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });

        if(location.href.indexOf('?') > -1) {
            var args = location.href.substring(location.href.indexOf('?')+1, location.length);
            var acct_id = gAcctId = args.substring(args.indexOf('=')+1, args.length);
            getAcct(acct_id);
        }
    });
    $(window).on('resize', function(){
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });
    });

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').prop('hidden', true);

    $('.book-btn').click(function(){
       window.location = location.origin + '/booker?aid='+ gAcctId; 
    });
}

//---------------------------------------------------------------------
function getAcct(acct_id) {
    /* Get account data, geolocation, and gift history.
       Split into 3 API calls to render cached data while querying the 
       rest from eTapestry.
    */

    api_call(
        'accounts/get/location',
        data={'acct_id':acct_id},
        displayMap);

    api_call(
        'accounts/get',
        data={'acct_id':acct_id},
        function(response) {
            if(response['status'] != 'success')
                return displayError('Account ID "'+acct_id+'" not found.', response);
            gAcct = response['data'];
            api_call(
                'accounts/gift_history',
                data={'ref':gAcct['ref']},
                displayDonationData);
            displayAcctData(gAcct);
        }
    );
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
    return;                
}

//------------------------------------------------------------------------------
function displayMap(response) {

    if(response['status'] != 'success')
        return;
    else
        $('#main').prop('hidden', false);

    var data = response['data'];
    var center = data['geometry'] ? data['geometry']['location'] : CITY_COORDS; 

    initGoogleMap(center, 12, map_style);
    console.log('Google Maps initialized');
    
    if(!data['geometry'])
        return;

    addMarker("Home", data['geometry']['location'], HOME_ICON);
}

//------------------------------------------------------------------------------
function displayDonationData(response) {
    /*Draw morris.js bar graph. 
    @gifts: list of simpliedifed eTapestry Gift objects w/ fields 'amount',
    'date', where 'date':{'$date':TIMESTAMP}. Sorted by descending date.
    */

    if(response['status'] != 'success' || ! response['data'] instanceof Array) {
        $('.chart-panel .panel-body').addClass("text-center").html("NO DONATION DATA FOUND");
        return;
    }

    console.log(format('Retrieved %s gifts', response['data'].length));
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
    $('.stat-box .loading').hide();
    $('.stat-box h1').prop('hidden',false);
    $('.stat-box div').prop('hidden',false);
    $('.chart-panel .loading').hide();
    $('.chart').prop('hidden',false);
    drawMorrisChart('chart', chart_data, 'date', ['value']);
    if(gifts.length > 0)
        $('#last-gave-d').html(new Date(gifts[0]['date']['$date']).strftime('%b %Y').toUpperCase());
    $('#timeline').prop('hidden',false);
}

//---------------------------------------------------------------------
function displayAcctData(acct) {

    if(!acct['accountDefinedValues'])
        return displayError('Invalid account type.', acct);

    $('#main').prop('hidden', false);

    /* PROFILE PANEL */
    $summary = $('#sum_panel');
    $summary.prop('hidden',false);
    $('#acct_name').html(acct['name']);
    $('#acct_id').html("#"+acct['id']);
    $('#status').html(getDV('Status', acct));

    /* PERSONAL DETAILS PANEL */
    $contact = $('#contact .row');
    $contact.empty();
    $('#contact_panel').prop('hidden',false);
    var details_flds = ['name', 'address', 'city', 'state', 'postalCode', 'email'];
    for(var i in details_flds) {
        var f = details_flds[i];
        if(acct.hasOwnProperty(f))
            addField(f.toTitleCase(), acct[f], $contact);
    }
    if(getPhone('Voice',acct))
        addField('Landline', getPhone('Voice',acct), $contact);
    if(getPhone('Mobile', acct))
        addField('Mobile', getPhone('Mobile',acct), $contact);

    var fa_clock = '<i class="fa fa-clock-o"></i>';
    var pcd = new Date(acct['personaCreatedDate']['$date']);
    $('#personaCreatedDate').html(
        toRelativeDateStr(pcd));
        //format("%s %s %s", pcd.strftime('%b %d, %Y '), fa_clock, pcd.strftime(' %I:%M %p')));
    if(acct['personaLastModifiedDate']) {
        var pmd = new Date(acct['personaLastModifiedDate']['$date']);
        $('#personaLastModifiedDate').html(
            toRelativeDateStr(pmd));
            //format("%s %s %s", pmd.strftime("%b %d, %Y "), fa_clock, pmd.strftime(" %I:%M %p")));
    }
    else
        $('#personaLastModifiedDate').html('Never');

    /* PICK-UP SERVICE PANEL */
    $custom = $('#custom .row');
    $custom.empty();
    $('#custom_panel').prop('hidden',false);

    var sm_dvs = [
        "Signup Date","Dropoff Date","Status","Next Pickup Date","Frequency", 
        "Neighborhood", "Reason Joined","Referrer","Date Cancelled","Block"];
    for(var i=0; i<sm_dvs.length; i++) {
        var dv = getDV(sm_dvs[i], acct);
        if(dv) addField(sm_dvs[i], dv, $custom);
    }
    var lg_dvs = ["Driver Notes", "Office Notes"];
    for(var i=0; i<lg_dvs.length; i++) {
        var dv = getDV(lg_dvs[i], acct);
        if(dv) addField(lg_dvs[i], dv, $custom, fullWidth=true);
    }
    var acd = new Date(acct['accountCreatedDate']['$date']);
    $('#accountCreatedDate').html(
        toRelativeDateStr(acd));
        //acd.strftime('%b %d, %Y ') + fa_clock + acd.strftime(' %I:%M %p'));
    if(acct['accountLastModifiedDate']) {
        var amd = new Date(acct['accountLastModifiedDate']['$date']);
        $('#accountLastModifiedDate').html(
            toRelativeDateStr(amd));
            //amd.strftime("%b %d, %Y ") + fa_clock + amd.strftime(" %I:%M %p"));
    }
    else
        $('#accountLastModifiedDate').html('Never');

    /* CHART PANEL */
    var dv_signup = getDV('Signup Date', acct);
    if(dv_signup)
        $('#joined-d').html(dv_signup.strftime("%b %Y").toUpperCase());

    /* ACTIONS PANEL */
    $('.act-panel').prop('hidden',false);
    var dv_sms = getDV('SMS', acct);
    if(!dv_sms)
        $('.chat-btn').addClass('disabled');
    else if(dv_sms) {
        var $chat_btn = $('.chat-btn');
        $chat_btn.click(showChatModal);
        $('#chat_modal').find('#send_sms').click(sendMessage);
        api_call(
            'alice/chatlogs',
            data={'mobile':dv_sms},
            function(response){
                console.log(response['data']);
                response['data']['account'] = gAcct;
                var $chat_btn = $('.chat-btn');
                $chat_btn.data('details', response['data']);
            });

    }

    /* INTERNAL PANEL */
    /*$internal = $('#internal .row');
    $internal.empty();
    $('#internal_panel').prop('hidden',false);
    var internal_flds = ['ref', 'id', 'primaryPersona', 'nameFormat'];
    for(var i=0; i<internal_fields.length; i++) {
        var field = internal_fields[i];
        if(field.indexOf('Date') > -1) {
            if(acct[field]) {
                var date = new Date(acct[field]['$date']).strftime('%b %d, %Y @ %H:%M');
            }
            else
                var date = 'None';
            addField(field, date, $internal);
        }
        else {
            addField(field, acct[field], $internal);
        }
    }*/
}

//------------------------------------------------------------------------------
function addField(name, value, $container, fullWidth=false) {

    var $lblDiv = $("<div class='pr-0 text-left'><label class='field align-top'></label></div>");
    var $valDiv = $("<div class='text-left'><label class='val align-top'></label></div>");

    if(fullWidth) {
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

    $lblDiv.find('label').html(name+': ');

    if(typeof value == "string")
        $valDiv.find('label').html(value.replace(/\\n/g, '  ').replace(/\*/g, ''));
    else if(value instanceof Date)
        $valDiv.find('label').html(value.strftime("%b %d, %Y"));
    else
        $valDiv.find('label').html(value);

    $container.append($lblDiv).append($valDiv);
}

/* Google Maps Styling */

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

//------------------------------------------------------------------------------
function addSocketIOHandlers() {

    var socketio_url = 'https://' + document.domain + ':' + location.port;
    var socket = io.connect(socketio_url);
    socket.on('connect', function(data){
        console.log('Socket.IO connected.');
    });
}

//------------------------------------------------------------------------------
function toRelativeDateStr(date) {

    var now = new Date();
    var diff_ms = now.getTime() - date.getTime();
    
    var min_ms = 1000 * 60;
    var hour_ms = 1000 * 3600;
    var day_ms = hour_ms * 24;
    var week_ms = day_ms * 7;
    var month_ms = day_ms * 30;
    var year_ms = day_ms * 365;

    if(diff_ms >= year_ms) {
        // Year(s) span
        var nYears = Number((diff_ms/year_ms).toFixed(0));
        return format("%s year%s ago", nYears, nYears > 1 ? 's' : '');
    }

    if(diff_ms >= month_ms) {
        // Month(s) span
        var nMonths = Number((diff_ms/month_ms).toFixed(0));
        return format("%s month%s ago", nMonths, nMonths > 1 ? 's' : '');
    }

    if(diff_ms >= week_ms) {
        // Week(s) span
        var nWeeks = Number((diff_ms/week_ms).toFixed(0));
        return format("%s week%s ago", nWeeks, nWeeks > 1 ? 's' : '');
    }
    
    if(diff_ms >= day_ms) {
        // Day(s) span
        var nDays = Number((diff_ms/day_ms).toFixed(0));
        return format("%s day%s ago", nDays, nDays > 1 ? 's' : '');
    }

    if(diff_ms >= hour_ms) {
        // Hour(s) span
        var nHours = Number((diff_ms/hour_ms).toFixed(0));
        return format("%s hour%s ago", nHours, nHours > 1 ? 's' : '');
    }

    if(diff_ms >= min_ms) {
        // Minute(s) span
        var nMin = Number((diff_ms/min_ms).toFixed(0));
        return format("%s minute%s ago", nMin, nMin > 1 ? 's' : '');
    }

    // Second(s) span
    var nSec = Number((diff_ms/1000).toFixed(0));
    return format("%s second%s ago", nSec, nSec > 1 ? 's' : '');
}
