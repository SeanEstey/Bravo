/* recent.js */

var list_item_styles = {
    'DEBUG': '',
    'INFO': 'list-group-item-info',
    'WARNING': 'list-group-item-warning',
    'ERROR': 'list-group-item-danger'
};

//------------------------------------------------------------------------------
function initRecent() {

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

    var filter_tags = ['sms_msg'];
    var badges = {
        'DEBUG': {'class': 'badge-default', 'text':'Debug'},
        'INFO': {'class': 'badge-info', 'text':'Info'},
        'WARNING': {'class': 'badge-warning', 'text':'Warning'},
        'ERROR': {'class': 'badge-danger', 'text':'Error'},
        'EXCEPTION': {'class':'badge-danger', 'text':'Exception'}
    };

    console.log("%s. %s events returned", resp['status'], resp['data'].length);
    var logs = resp['data'];
    $('#recnt_list').empty();

    for(var i=0; i<logs.length; i++) {
        if(logs[i]['tag'] && filter_tags.indexOf(logs[i]['tag']) > -1)
                continue;

        $evnt_item = $('#event_item').clone().prop('id', 'list_grp_'+String(i));
        $evnt_item.find('#event_msg').html(logs[i]['message']);
        $evnt_item.find('#event_dt').html(
            new Date(logs[i]['timestamp']['$date'])
                .strftime('%b %d at %I:%M%p'));
        $evnt_item.click(showLogEntryDetailsModal);
        $evnt_item.prop('hidden', false);
        $evnt_item.find('.badge').addClass(badges[logs[i]['level']]['class']);
        $evnt_item.find('.badge').html(badges[logs[i]['level']]['text']);
        $('#recnt_list').append($evnt_item);

        $evnt_item.data("details", logs[i]); // Save for viewing in Modal
        logs[i]['timestamp'] = new Date(logs[i]['timestamp']['$date']).strftime('%b %d at %I:%M %p');
        delete logs[i]['asctime'];
    }
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
    else if(typeof value === 'string') {
        div += value.replace(/\n/g, '<br>').replace(/\s\s\s\s/g, '&nbsp&nbsp&nbsp&nbsp') + '</DIV>';
    }
    else
        div += value + '</DIV>';

    container.append(div);
}
