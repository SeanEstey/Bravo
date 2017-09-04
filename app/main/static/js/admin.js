/* main/static/js/admin.js */

var serv_pane_init = false;
var prop_pane_init = false;
var user_pane_init = false;
var alice_pane_init = false;
var recnt_pane_init = false;

//------------------------------------------------------------------------------
function init() {

    //$('#admin-nav').prop('hidden',false);
    $('#admin-nav').addClass('d-flex');
    $('#admin-nav').show();
    $('.br-alert').hide();

    initPropertiesPane();
    initPreviewerPane();

    $('.nav-pills a').click(function (e){
        e.preventDefault();
        console.log('active tab %s', $(this).prop('hash'));
        var id = $(this).prop('hash');

        if(id == '#services') {
            initServicesPane();
        }
        else if(id == '#leaderboard') {
            initLeaderboardPane();
        }
        else if(id == '#stats') {
            initPropertiesPane();
        }
        else if(id == '#me') {
            initUserPane();
        }
        else if(id == '#recent') {
            window.location = "https://bravoweb.ca/recent";
        }
        else if(id == '#analytics') {
            window.location = "https://bravoweb.ca/analytics";
        }
        else if(id == "#map_analyzer") {
            window.location = "https://bravoweb.ca/tools";
        }

        $(this).tab('show');
    })
}

//------------------------------------------------------------------------------
function initUserPane() {

    if(user_pane_init)
        return;

    //$("[name='adm_panl_check']").bootstrapSwitch();

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
          //console.log(response['status']);
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

    api_call('group/properties/get', null, function(response){
        console.log('Received stats data');
        var prop = response['data'];

        $("#n_donors").text(Sugar.Number.abbr(prop['n_donors'],1));
        $("#n_alice_convos").text(Sugar.Number.abbr(prop['n_alice_convos'],1));
        $("#n_alice_incoming").text(Sugar.Number.abbr(prop['n_alice_incoming'],1));
        $("#n_maps_indexed").text(prop['n_maps_indexed']);
        $("#n_notific_events").text(prop['n_notific_events']);
        $("#n_leaderboard_accts").text(prop['n_leaderboard_accts']);
        $("#n_users").text(prop['n_users']);

        var free = prop['sys_mem']['free'];
        var total = prop['sys_mem']['total'];
        var perc = (100-((free/total)*100)).toFixed(0);
        $("#sys_mem").text(format("%s%", perc)); //free, total));
        $("#db_size").text((prop['db_stats']['dataSize']/1000000).toFixed(0)+'m');
        $("#n_sessions").text(Sugar.Number.abbr(prop['n_sessions'],1));
        $("#n_cached_accounts").text(Sugar.Number.abbr(prop['n_cached_accounts'],1));
        $("#n_cached_geolocations").text(Sugar.Number.abbr(prop['n_geolocations'],1));
        $("#n_cached_gifts").text(Sugar.Number.abbr(prop['n_cached_gifts'],1));

        prop_pane_init = true;
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
