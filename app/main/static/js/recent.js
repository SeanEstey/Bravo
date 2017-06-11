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
        $('#'+id).click(showLogEntryDetailsModal);
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
