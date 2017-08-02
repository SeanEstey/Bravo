/* recent.js */

var list_item_styles = {
    'DEBUG': '',
    'INFO': 'list-group-item-info',
    'WARNING': 'list-group-item-warning',
    'ERROR': 'list-group-item-danger'
};

grp_keys = {
    'grp-org': 'org_name',
    'grp-sys': 'sys',
    'grp-other':'anon'
};
lvl_keys = {
    'lvl-debug':'DEBUG',
    'lvl-info':'INFO',
    'lvl-warn':'WARNING',
    'lvl-err':'ERROR'
};
tag_keys = {
    'tag-api':'api',
    'tag-task':'task'
};

//------------------------------------------------------------------------------
function initRecent() {

    requestLogEntries();

    $('#filterMenu .dropdown-item').click(toggleFilter)
        .find('.dropdown-menu').show();
}

//------------------------------------------------------------------------------
function toggleFilter(e) {

    e.preventDefault();
    e.stopPropagation();

    $a = $(this);

    if($a.prop('id') == 'grp-all') {
        for(var k in grp_keys) {
            $('#'+k+ ' i').addClass('fa-check');
        }
    }
    else if($a.prop('id') == 'lvl-all') {
        for(var k in lvl_keys) {
            $('#'+k+ ' i').addClass('fa-check');
        }
    }
    else if($a.find('i').hasClass('fa-check'))
        $a.find('i').removeClass('fa-check');
    else
        $a.find('i').addClass('fa-check');

    $('#filterMenu .dropdown-menu').show();
    $('#filterMenu .dropdown-menu').prop('display', 'block');

    requestLogEntries();
}

//------------------------------------------------------------------------------
function requestLogEntries() {

    // Get list of checked filter ID's
    var checked = [];
    $('#filterMenu .dropdown-menu i.fa-check').parent().each(function(){
        checked.push($(this).prop('id'));
    });

    var data = {
        'levels':[],
        'groups':[],
        'tags':[]
    };

    // Translate date, call API to retrieve logs

    for(var k in grp_keys) {
        if(checked.indexOf(k) > -1)
            data['groups'].push(grp_keys[k]);
    }

    for(var k in lvl_keys) {
        if(checked.indexOf(k) > -1)
            data['levels'].push(lvl_keys[k]);
    }

    for(var k in tag_keys) {
        if(checked.indexOf(k) > -1)
            data['tags'].push(tag_keys[k]);
    }

    data['levels'] = JSON.stringify(data['levels']);
    data['groups'] = JSON.stringify(data['groups']);
    data['tags'] = JSON.stringify(data['tags']);

    //console.log('data='+JSON.stringify(data));

    api_call('logger/new_get', data=data, renderLogEntries);
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
