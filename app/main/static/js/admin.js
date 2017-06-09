
var serv_pane_init = false;
var prop_pane_init = false;
var user_pane_init = false;
var alice_pane_init = false;
var recnt_pane_init = false;
var list_item_styles = {
    'DEBUG': '',
    'INFO': 'list-group-item-info',
    'WARNING': 'list-group-item-warning',
    'ERROR': 'list-group-item-danger'
};

//------------------------------------------------------------------------------
function init() {

    // Init default pane
    initUserPane();
    initPreviewerPane();

    $('.nav-tabs a').click(function (e){
        e.preventDefault();
        console.log('active tab %s', $(this).prop('hash'));
        var id = $(this).prop('hash');

        if(id == '#services') {
            initServicesPane();
        }
        else if(id == '#leaderboard') {
            initLeaderboardPane();
        }
        else if(id == '#properties') {
            initPropertiesPane();
        }
        else if(id == '#me') {
            initUserPane();
        }
        else if(id == '#alice') {
            initAlicePane();
        }
        else if(id == '#recent') {
            initRecentPane();
        }

        $(this).tab('show');
    })
}

//------------------------------------------------------------------------------
function initUserPane() {

    if(user_pane_init)
        return;

    $("[name='adm_panl_check']").bootstrapSwitch();

    api_call(
      'user/get',
      data=null,
      function(response){
          var user = response['data'];
          console.log(user);
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
      'agency/conf/get',
      null,
      function(response){
          console.log(response['status']);
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

    api_call('agency/properties/get', null, function(response){
        console.log(response['status']);
        var prop = response['data'];

        $("#n_alice_convos").text(prop['n_alice_convos']);
        $("#n_maps_indexed").text(prop['n_maps_indexed']);
        $("#n_notific_events").text(prop['n_notific_events']);
        $("#n_leaderboard_accts").text(prop['n_leaderboard_accts']);
        $("#n_users").text(prop['n_users']);
        $("#n_sessions").text(prop['n_sessions']);

        prop_pane_init = true;
    });
}

//------------------------------------------------------------------------------
function initAlicePane() {

    if(alice_pane_init)
        return;

    // Retrieve chatlogs JSON
    api_call('alice/chatlogs', data={}, renderChatEntries);
}

//------------------------------------------------------------------------------
function renderChatEntries(resp){
    /* Render list-items displaying abbreviated user chat data.
     * Clicking on list-items shows a Modal dialog with full chat data.
     */

    var MAX_PREVIEW_LINES = 3;
    var strftime = "%b %d @ %I:%M%p";
    alice_pane_init = true;
    var chat_data = resp['data'];
    $('#convo_list').empty();

    console.log("%s chats (%s)", resp['data'].length, resp['status']);

    for(var i=0; i<chat_data.length; i++) {
        var id = "item_" + String(i);
        var user_chat = chat_data[i];
        var lines = '';
        var n_msgs = user_chat['messages'].length;
        var card = '';
        
        // Chat data -> HTML string
        for(var j=n_msgs-1; j>=0; j--) {
            var msg = user_chat['messages'][j];

            if(msg['direction'] == 'out')
                continue;
            
            var date_str = new Date(msg["timestamp"]["$date"]).strftime(strftime);

            if(user_chat['account'])
                var name = user_chat['account']['name'];
            else
                var name = 'Unregistered User (' + user_chat['mobile'] + ')';

            card = $(
              '<a href="#" id="'+id+'" style="margin:0.1em; text-decoration:none;" class="justify-content-between">' +
                '<div ' +
                    'class="card list-group-item list-group-item-action ' + 
                    'style="width:100%" ' +
                    'onmouseover="this.style.color=\'#0275d8\'; this.style.background=\'white\'" ' +
                    'onmouseout="this.style.color=\'gray\'"> ' +
                  '<div class="card-block" style="padding-bottom:0; padding-top:0">' +
                    '<h4 style="" class="card-title">'+ name + '</h4>' +
                    '<span class="card-text">Last Message: "'+ msg['message'] +'"</span>' +
                    '<p class="card-text">'+ date_str +'</p>' +
                  '</div>' +
                  '<h5><span class="badge badge-default badge-pill">'+n_msgs+'</span></h5>' +
                '</div>' +
              '</a>'
            );
            break;
        }

        card.click(showChatlogModal);
        card.data("details", user_chat);
        $('#convo_list').append(card);
    }
}

//------------------------------------------------------------------------------
function showChatlogModal(e) {

    e.preventDefault();

    var color =  {
        "out": "text-primary",
        "in": "text-success"};
    var DATE_FRMT = "%b %d: %I:%M%p";
    var user_chat = $(this).data('details');

    if(user_chat['account'])
        var name = user_chat['account']['name'];
    else
        var name = 'Unregistered User (' + user_chat['mobile'] + ')';

    var container = $(
      '<div>' +
        '<div><b>User</b>: '+name+'</div>' +
        '<div><b>Mobile</b>: '+user_chat['mobile']+'</div>' +
        '<div><b>Message History</b></div>' + 
      '</div>'
    );
    messages_tbl = $(
      '<table id="chatlog" class="table table-responsive table-sm" style="max-height:300px">' +
      '</table>'
    );
    
    for(var i=0; i<user_chat['messages'].length; i++) {
        var msg = user_chat['messages'][i];
        var date_str = new Date(msg["timestamp"]["$date"]).strftime(DATE_FRMT);

        messages_tbl.append(
          '<tr>' + 
            '<td nowrap style="padding:0; padding-right:0.25em; border:none" class="text-muted">'+ date_str +': </td>' +
            '<td style="border:none; padding:0;" class="'+ color[msg['direction']] +'">'+ msg['message'] +'</td>' +
          '</tr>'
        );
    }

    container.append(messages_tbl);

    $('#log_modal').on('shown.bs.modal', function () {
        $('#chatlog').scrollTop($('#chatlog')[0].scrollHeight);
    })

    showModal(
      'log_modal',
      'Chat History',
      container,
      null,
      'Ok');
}

//------------------------------------------------------------------------------
function initRecentPane() {

    if(recnt_pane_init)
        return;
    else
        recnt_pane_init = true;

	$('#filtr_lvls input').change(function() {
        console.log('%s=%s', $(this).prop('name'), $(this).prop('checked'));	
        requestLogEntries();
	});

	$('#filtr_grps input').change(function() {
        console.log('%s=%s', $(this).prop('name'), $(this).prop('checked'));	
        requestLogEntries();
	});

    requestLogEntries();
}

//------------------------------------------------------------------------------
function requestLogEntries() {

    api_call(
        'logger/get',
        data = {
            'levels': JSON.stringify($('#filtr_lvls').serializeArray()),
            'groups': JSON.stringify($('#filtr_grps').serializeArray())
        },
        renderLogEntries
    );
}

//------------------------------------------------------------------------------
function renderLogEntries(resp) {

    console.log("%s. %s events returned", resp['status'], resp['data'].length);
    var logs = resp['data'];
    $('#recnt_list').empty();

    for(var i=0; i<logs.length; i++) {
        var id = "list_grp_" + String(i);

        $('#recnt_list').append(
            '<a href="#" ' +
            'id=' + id + ' ' +
            'class="list-group-item list-group-item-action ' + list_item_styles[logs[i]['level']] + '">' +
            new Date(logs[i]["timestamp"]["$date"]).strftime("%b %d: %I:%M%p: ") + logs[i]["message"] +
            '</a>'
        );

        logs[i]['timestamp'] = new Date(logs[i]['timestamp']['$date']).strftime('%b %d, %I:%M %p');
        delete logs[i]['asctime'];
        $('#'+id).data("details", logs[i]); // Save for viewing in Modal
    }

    $('.list-group-item').click(showLogEntryDetailsModal);
}

//------------------------------------------------------------------------------
function showLogEntryDetailsModal(e) {

    var std_fields = [
        "message",
        "user", "group", "level", "process", "processName", "thread", "threadName",
        "loggerName", "module", "fileName", "method", "lineNumber", "exception", "timestamp"
    ];

    e.preventDefault();

    var log_record = $(this).data('details');
    var container = $('<div></div>');

    appendLogField('message', log_record['message'], container);

    for(var field in log_record) {
        if(std_fields.indexOf(field) == -1)
            appendLogField(field, log_record[field], container);
    }

    container.append('<div><br></div>');

    for(var i=1; i<std_fields.length; i++){
        var field = std_fields[i];

        if(log_record.hasOwnProperty(field))
            appendLogField(field, log_record[field], container);
    }

    showModal(
      'log_modal',
      'Event Details',
      container,
      null,
      'Ok');
}

//------------------------------------------------------------------------------
function appendLogField(field, value, container) {

    if(!value)
        return;

    var div = "<DIV><B>" + field + "</B>: ";

    if(typeof value === 'object')
        div += 
            '<PRE style="white-space:pre-wrap">' + 
                JSON.stringify(value, null, 2)
                    .replace(/\\n/g, "<BR>") +
            '</PRE>' +
          '</DIV>';
    else
        div += value + '</DIV>';

    container.append(div);
}

//------------------------------------------------------------------------------
function saveFieldEdit(field, value) {

    api_call(
        'agency/conf/update',
        {'field':field, 'value':value},
        function(response) {
            if(response['status'] != 'success')
                alertMsg(response['status'], 'danger');
            else
                alertMsg('Edited field successfully', 'success');
        }
    );
}
