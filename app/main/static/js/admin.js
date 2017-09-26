/* main/static/js/admin.js */

var serv_pane_init = false;
var prop_pane_init = false;
var user_pane_init = false;
var alice_pane_init = false;
var recnt_pane_init = false;

//------------------------------------------------------------------------------
function init() {
    $('#admin-nav').addClass('d-flex');
    $('#admin-nav').show();
    $('.br-alert').hide();
    initPropertiesPane();
    initPreviewerPane();

    $('.nav-pills a').click(function (e){
        e.preventDefault();
        console.log('active tab %s', $(this).prop('hash'));
        var id = $(this).prop('hash');
        if(id == '#services')
            initServicesPane();
        else if(id == '#leaderboard')
            initLeaderboardPane();
        else if(id == '#stats')
            initPropertiesPane();
        else if(id == '#me')
            initUserPane();
        else if(id == '#recent')
            window.location = "https://bravoweb.ca/recent";
        else if(id == '#analytics')
            window.location = "https://bravoweb.ca/analytics";
        else if(id == "#map_analyzer")
            window.location = "https://bravoweb.ca/tools";
        else if(id == "#datatable")
            window.location = "https://bravoweb.ca/datatable";
        $(this).tab('show');
    })
}

//------------------------------------------------------------------------------
function initUserPane() {
    if(user_pane_init)
        return;

    api_call(
      'user/get',
      data=null,
      function(response){
          var user = response['data'];
          //console.log(user);
          $("#user_form [id='first_name']").text(user['name']);
          $("#user_form [id='user_name']").text(user['user_id']);
          $("#user_form [id='is_admin']").text(user['admin']);
      });
    $('#logout').click(function(e){
        e.preventDefault();
        api_call(
            'user/logout',
            data=null,
            function(response){
                console.log(response['status']);
                var msg = "You've been logged out successfully.";
                location.href = $URL_ROOT+'/login?msg='+encodeURIComponent(msg);
            }
        );
    });
    user_pane_init = true;
}

//------------------------------------------------------------------------------
function initServicesPane() {
    if(serv_pane_init)
        return;
    $('#service_acct').tooltip();
    $('#linked_cal').tooltip();

    api_call(
      'group/conf/get',
      null,
      function(response){
          var conf = response['data'];
          $("#crm_org_name").text(conf['etapestry']['org_name']);
          $("#crm_acct_id").text(conf['etapestry']['user']);
          $("#routing_acct_id").text(conf['routing']['routific']['acct_id']);
          $("#twilio_acct_id").text(conf['twilio']['acct_id']);
          $("#phone_number").text(conf['twilio']['sms']['number']);
          $("#mailgun_acct_id").text(conf['mailgun']['acct_id']);
          $("#sched_delta_days").val(conf['notify']['sched_delta_days']);
          $("#email_fire_days_delta").val(conf['notify']['triggers']['email']['fire_days_delta']);
          $("#email_fire_hour").val(conf['notify']['triggers']['email']['fire_hour']);
          $("#voice_sms_fire_days_delta").val(conf['notify']['triggers']['voice_sms']['fire_days_delta']);
          $("#voice_sms_fire_hour").val(conf['notify']['triggers']['voice_sms']['fire_hour']);
          serv_pane_init = true;
      });
}

//------------------------------------------------------------------------------
function initPreviewerPane() {
    // Button handlers
    $('#receipt_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send Email',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#receipt_form').serialize();

        api_call(
          'accounts/preview_receipt',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          });
    });
    $('#sms_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send SMS',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#sms_notific_form').serialize();

        api_call(
          'notify/preview/sms',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          }
        );
    });
    $('#email_notific_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send Email',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#email_notific_form').serialize();

        api_call(
          'notify/preview/email',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          }
        );
    });
}

//------------------------------------------------------------------------------
function initLeaderboardPane() {
    if($('#leaderboard').children().length > 0)
        return;

    api_call(
      'leaderboard/get',
      null,
      function(response){
          console.log('API: leaderboard/get: %s', response['status']);
          var rankings = response['data'];

          for(var i=0; i<rankings.length; i++) {
              var div = 
                "<div>#" + (i+1) + "    " + rankings[i]['_id'] + ": $" + rankings[i]['ytd'] +"</div>";
              $('#leaderboard').append(div);
          }
      }
    );
}

//------------------------------------------------------------------------------
function initPropertiesPane() {
    if(prop_pane_init)
        return;
    var abbr = Sugar.Number.abbr;
    var num_frmt = Sugar.Number.format;

    var sections = [
        {
            'parent_id':'recent-contnr',
            'fields': {
                'nGifts': 'Gifts',
                'revenue': 'Gift Value',
                'collRate': 'Collection Rate',
                'nNewDonors': 'New Accounts',
                'nDonorLoss': 'Lost Accounts'
            }
        },
        {
            'parent_id':'overall-contnr',
            'fields':{
                'nDonors': 'Active Donors',
                'nMobile':'Mobile Numbers',
                'nConvos':'Alice Convos',
                'nIncSMS':'Alice Replies',
            },
        },
        {
            'parent_id':'indexed-contnr',
            'fields': {
                'nDbAccts': 'Accounts',
                'nDbGeoloc': 'Geolocations',
                'nDbGifts': 'Gifts',
                'nDbMaps': 'Maps',
            }
        },

        {
            'parent_id':'sysmon-contnr',
            'fields': {
                'DbSize': 'Database Size (MB)',
                'sysMem': 'Mem Usage'
            }
        }
    ]

    // Insert Stat cards into DOM
    for(var i=0; i<sections.length;i++) {
        for(var k in sections[i]['fields']) {
            var $card = $('#stat-card').clone().prop('id',k).show();
            $card.find('.admin-lbl').text(sections[i]['fields'][k]);
            $('#'+sections[i]['parent_id']).append($card);
        }
    }

    var mth_time = Number((Sugar.Date.create("a month ago").getTime()/1000).toFixed(0));
    var now_time = Number((Sugar.Date.create("today").getTime()/1000).toFixed(0));

    // Query analytics API and populate data
    api_call(
        'analytics/summary',
        null, 
        function(response){
            prop_pane_init = true;
            var r = response['data'];
            var free = r['sysMem']['free'];
            var total = r['sysMem']['total'];
            var perc = (100-((free/total)*100)).toFixed(0);

            $("#nDonors .admin-stat").text(abbr(r['nDonors'],1));
            $('#nDonors').tooltip({'title':num_frmt(r['nDonors'],0)});
            $('#nMobile .admin-stat').text(abbr(r['nMobile'],1));
            $('#nMobile').tooltip({'title':num_frmt(r['nMobile'],0)});
            $("#nConvos .admin-stat").text(abbr(r['nConvos'],1));
            $('#nConvos').tooltip({'title':num_frmt(r['nConvos'],0)});
            $("#nIncSMS .admin-stat").text(abbr(r['nIncSMS'],1));
            $('#nIncSMS').tooltip({'title':num_frmt(r['nIncSMS'],0)});
            $("#nDbAccts .admin-stat").text(abbr(r['nDbAccts'],1));
            $('#nDbAccts').tooltip({'title':num_frmt(r['nDbAccts'],0)});
            $("#nDbGeoloc .admin-stat").text(abbr(r['nDbGeoloc'],1));
            $("#nDbGifts .admin-stat").text(abbr(r['nDbGifts'],1));
            $('#nDbGifts').tooltip({'title':num_frmt(r['nDbGifts'],0)});
            $("#DbSize .admin-stat").text((r['dbStats']['dataSize']/1000000).toFixed(0)+'m');
            $("#nDbMaps .admin-stat").text(r['nDbMaps']);
            $("#sysMem .admin-stat").text(format("%s%", perc));
    });
    api_call(
        'analytics/growth',
        data={'start':mth_time, 'end':now_time},
        function(response) {
            var r = response['data'];
            var n_lost=0, n_new = 0;
            for(var k in r['growth'])
                n_new += r['growth'][k];
            for(var k in r['attrition'])
                n_lost += r['attrition'][k];
            $("#nNewDonors .admin-stat").text(abbr(n_new,1));
            $('#nNewDonors').tooltip({'title':num_frmt(n_new,0)});
            $("#nDonorLoss .admin-stat").text(abbr(n_lost,1));
            $('#nDonorLoss').tooltip({'title':num_frmt(n_lost,0)});
        }
    );
    api_call(
        'analytics/aggregate',
        data={start:mth_time, end:now_time, field:'collectionRate', op:'avg', options:{'prefix':'R'}},
        function(r) {
            $("#collRate .admin-stat").text(num_frmt(r['data']['result']*100,0)+'%');
    });
    api_call(
        'analytics/aggregate',
        data={start:mth_time, end:now_time, field:'estimateTotal', op:'sum'},
        function(r) {
            $("#revenue .admin-stat").text('$'+abbr(r['data']['result'],1));
            $("#revenue").tooltip({'title':num_frmt(r['data']['result'],0)});
    });
    api_call(
        'analytics/aggregate',
        data={start:mth_time, end:now_time, field:'nDonations', op:'sum'},
        function(r) {
            $("#nGifts .admin-stat").text(abbr(r['data']['result'],1));
            $("#nGifts").tooltip({'title':num_frmt(r['data']['result'],0)});
    });
}

//------------------------------------------------------------------------------
function saveFieldEdit(field, value) {
    api_call(
        'group/conf/update',
        {'field':field, 'value':value},
        function(response) {
            if(response['status'] != 'success')
                alertMsg(response['status'], 'danger');
            else
                alertMsg('Edited field successfully', 'success');
        }
    );
}
