/* accounts.js */

gAcctId = null;
gAcct = null;
gGeolocation = null;
gMobile = null;

//-----------------------------------------------------------------------------
function accountsInit() {

    if(location.href.indexOf('?') > -1) {
        var args = location.href.substring(
            location.href.indexOf('?')+1, location.length);
        var acct_id = gAcctId = args.substring(
            args.indexOf('=')+1, args.length);
        $('#acct_name').tooltip({'title': "Account ID: "+acct_id});
        getAcct(acct_id);
    }

    $(document).ready(function() {
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });


    });
    $(window).on('resize', function(){
        $(".setsize").each(function() {
            $(this).height($(this).width());
        });
    });

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').first().prop('id','top-alert');

    $('.book-btn').click(function(){
       window.location = location.origin + '/booker?aid='+ gAcctId; 
    });

    $('#pus-edit').click(toggleEditMode);
    $('#info-edit').click(toggleEditMode);
    $('#edit-confirm button.btn-danger').click(toggleEditMode);
    $('#edit-confirm button.btn-success').click(submitEdits);
}

//-----------------------------------------------------------------------------
function submitEdits() {
    
    var $form = $(this).closest('form');
    var values = {};

    $.each($form.serializeArray(), function(_, kv) {
      values[kv.name] = kv.value;
    }); 

    var data = {
        'acct_id':Number(gAcctId)
    };

    // DV's
    if($form.closest('.hpanel').prop('id') == 'custom_panel') {
        if(values.hasOwnProperty('Block'))
            values['Block'] = values['Block'].replace(/\s/g,'');
        data['udf'] = JSON.stringify(values);

    }
    // Persona
    else {
        if(values['Mobile'] || values['Voice']) {
            // Update 'SMS' DV with Mobile number in international
            // format so Alice can identify the account when
            // receiving 
            if(values['Mobile']) {
                var numeric = /\s|\-|\(|\)|[a-zA-Z]/g;
                data['udf'] = {
                    'SMS': format('+1%s', values['Mobile'].replace(numeric,''))
                };

            }
            values['phones'] = [
                {'type':'Mobile','number':values['Mobile'] || ''},
                {'type':'Voice', 'number':values['Voice'] || ''}
            ];
            delete values['Mobile'];
            delete values['Voice'];
        }

        data['persona'] = JSON.stringify(values);
    }

    console.log(data);

    api_call(
        'accounts/update',
        data=data,
        function(response) {
            console.log(response);
            //var response = response['responseJSON']; 

            if(response['status'] == 'success') {
                $('#top-alert').prop('hidden', false);
                alertMsg("Account updated successfully.", "success");
                toggleEditMode(null, panel=$form.closest('.hpanel'));
                //window.location = window.location;
            }
            else {
                $('#top-alert').prop('hidden', false);
                alertMsg("Account update failed (" + response['desc'] + ")", "danger", id='top-alert');
            }
        });
}


//---------------------------------------------------------------------
function toggleEditMode(e, panel=null) {

    if(panel)
        var $panel = panel;
    else
        var $panel = $(this).closest('.hpanel');

    // Turn Edit mode ON
    if($panel.find('form input').length == 0) {
        $panel.find('.panel-footer').prop('hidden', true);
        $panel.find('#edit-confirm div').prop('hidden',false);
        var $each = $panel.find('.panel-body label.val');
        var $replace = $('<input type="text" class="form-control my-1"></input>');
        $panel.find('form div:hidden').prop('hidden',false);
    }
    // Turn Edit mode OFF
    else {
        $panel.find('.panel-footer').prop('hidden', false);
        $panel.find('#edit-confirm div').prop('hidden', true);
        var $each = $panel.find('.panel-body input');
        var $replace = $('<label class="val"></label>');
    }

    $each.each(function() {
        var $par_div = $(this).parent();
        var value = $replace.is('label') ? $(this).val() : $(this).text();
        var width = $(this).width()*.90;
        var id = $(this).prop('id');
        $par_div.empty();

        if($replace.is('label')) {
            $par_div.append($replace.clone().prop('id', id).text(value));
        }
        else if($replace.is('input')) {
            var $input = $replace.clone()
                .prop('id',id)
                .val(value)
                .prop('name', id)
                .data('orig_val', value);
            $par_div.append($input);
            $par_div.prop('hidden', false);
        }
    });
}

//---------------------------------------------------------------------
function displaySchedule(response) {

    var dates = response['data'];

    for(d in dates) {
        // Dates are in UTC. Build Date obj using UTC values
        var date = new Date(
            d.getUTCFullYear(),
            d.getUTCMonth(),
            d.getUTCDate(),
            d.getUTCHours(),
            d.getUTCMinutes(),
            d.getUTCSeconds()
        );
        console.log(date);
    }
}

//---------------------------------------------------------------------
function getAcct(acct_id) {
    /* Get account data, geolocation, and gift history.
       Split into 3 API calls to render cached data while querying the 
       rest from eTapestry.
    */

    $('.refresh-btn').click(function() {
        api_call(
            'accounts/get',
            data={'acct_id':gAcctId,'cached':false},
            function(response) {
                displayAcctData(response['data']);
            }
        );
    });

    /*
    api_call(
        'accounts/get/schedule',
        data={'acct_id':acct_id},
        displaySchedule);
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
    console.log(format('Map initialized, t=%sms', Sugar.Date.millisecondsAgo(a)));
    
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

    console.log(format('%s gifts retrieved, t=%sms', response['data'].length, Sugar.Date.millisecondsAgo(a)));
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
            'label': gifts[i]['note']
        });

        if(gifts[i]['amount'] > 0)
            total += gifts[i]['amount'];
        else
            n_gifts--;
    }

    //total = total.toFixed(2);
    if(n_gifts > 0)
        var avg_gift = (total/n_gifts); 
    else
        var avg_gift = 0.0;

    // Render summary info
    $('#n_gifts').html(n_gifts);
    $('#avg .float').html('$'+ Sugar.Number.abbr(avg_gift,0));
    $('#total .float').html('$' + Sugar.Number.abbr(total,2));

    $('.stats-row .loading').hide();
    $('.stats-row .stats-val').prop('hidden',false).show();
    $('.stats-row .stats-lbl').prop('hidden',false).show();
    $('.chart-panel .loading').hide();

    if(gifts.length > 0) {
        $('.chart').prop('hidden',false);

        drawMorrisBarChart(
            'chart', chart_data, 'date', ['value'], options=
            {'labelTop':true, 'axes':false,
             'hoverCallback': function(index,options,content) {
                var data=options.data[index];
                $(".morris-hover").html('<div>Custom label: '+data.label+'</div>');
                var label = data['date']+'<br>$'+data.value+'<br>'+data.label;
                return label;
            }});

        $('#last-gave-d').html(new Date(gifts[0]['date']['$date'])
            .strftime('%b %Y').toUpperCase());

        console.log(format('Chart rendered, t=%sms', Sugar.Date.millisecondsAgo(a)));
    }
    else {
        $('.chart').prop('hidden',false);
        $('.chart').addClass('d-flex');
        $('.chart').css('align-items', 'center');
        var $no_gifts = $('<h4 class="mx-auto">No Gifts</h4>');
        $('.chart').append($no_gifts);
    }

    $('#timeline').prop('hidden',false);
}

//-----------------------------------------------------------------------------
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
            addField(f, acct[f], $contact);
    }
    addField('Voice', getPhone('Voice',acct) || '', $contact);
    addField('Mobile', getPhone('Mobile',acct || ''), $contact);

    var fa_clock = '<i class="fa fa-clock-o"></i>';
    var pcd = new Date(acct['personaCreatedDate']['$date']);
    $('#personaCreatedDate').html(toRelativeDateStr(pcd));
    if(acct['personaLastModifiedDate']) {
        var pmd = new Date(acct['personaLastModifiedDate']['$date']);
        $('#personaLastModifiedDate').html(toRelativeDateStr(pmd));
    }
    else
        $('#personaLastModifiedDate').html('Never');

    /* PICK-UP SERVICE PANEL */
    $custom = $('#custom .row');
    $custom.empty();
    $('#custom_panel').prop('hidden',false);

    var sm_dvs = [
        "Signup Date","Dropoff Date","Status","Next Pickup Date","Frequency", 
        "Neighborhood", "Reason Joined","Referrer","Date Cancelled","Block", "SMS"];
    for(var i=0; i<sm_dvs.length; i++) {
        var dv = getDV(sm_dvs[i], acct) || '';
        addField(sm_dvs[i], dv, $custom);
    }
    var lg_dvs = ["Driver Notes", "Office Notes"];
    for(var i=0; i<lg_dvs.length; i++) {
        var dv = getDV(lg_dvs[i], acct) || '';
        addField(lg_dvs[i], dv, $custom, fullWidth=true);
    }
    var acd = new Date(acct['accountCreatedDate']['$date']);
    $('#accountCreatedDate').html(toRelativeDateStr(acd));
    if(acct['accountLastModifiedDate']) {
        var amd = new Date(acct['accountLastModifiedDate']['$date']);
        $('#accountLastModifiedDate').html(toRelativeDateStr(amd));
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
                //console.log(response['data']);
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

//-----------------------------------------------------------------------------
function addField(name, value, $container, fullWidth=false) {

    var $lblDiv = $("<div class='pr-0 text-left'><label class='field align-top'></label></div>");
    var $valDiv = $("<div class='text-left'><label class='val align-top' id='"+name+"'></label></div>");

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

    $lblDiv.find('label').html(name.toTitleCase()+': ');

    //if(typeof value == "string")
    //    $valDiv.find('label').html(value.replace(/\\n/g, '  ').replace(/\*/g, ''));
    //else if(value instanceof Date)
    //    $valDiv.find('label').html(value.strftime("%b %d, %Y"));
    if(value instanceof Date)
        $valDiv.find('label').html(value.strftime("%d/%m/%Y"));
    else
        $valDiv.find('label').html(value);

    if(!value) {
        $lblDiv.prop('hidden', true);
        $valDiv.prop('hidden', true);
    }
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
