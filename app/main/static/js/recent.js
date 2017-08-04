/* recent.js */

var list_item_styles = {
    'DEBUG': '',
    'INFO': 'list-group-item-info',
    'WARNING': 'list-group-item-warning',
    'ERROR': 'list-group-item-danger'
};

var grp_keys = {
    'grp-org': 'org_name',
    'grp-sys': 'sys',
    'grp-other':'anon'
};
var lvl_keys = {
    'lvl-debug':'DEBUG',
    'lvl-info':'INFO',
    'lvl-warn':'WARNING',
    'lvl-err':'ERROR'
};
var tag_keys = {
    'tag-api':'api',
    'tag-task':'task'
};

//------------------------------------------------------------------------------
function initRecent() {

    $('.br-alert').prop('hidden', true);
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
            $('#'+k+ ' i').removeClass('fa-square-o').addClass('fa-check-square-o');
        }
    }
    else if($a.prop('id') == 'lvl-all') {
        for(var k in lvl_keys) {
            $('#'+k+ ' i').removeClass('fa-square-o').addClass('fa-check-square-o');
        }
    }
    else if($a.find('i').hasClass('fa-check-square-o')) {
        $a.find('i')
            .removeClass('fa-check-square-o')
            .addClass('fa-square-o');
    }
    else
        $a.find('i').removeClass('fa-square-o').addClass('fa-check-square-o');

    $('#filterMenu .dropdown-menu').show();
    $('#filterMenu .dropdown-menu').prop('display', 'block');

    requestLogEntries();
}

//------------------------------------------------------------------------------
function requestLogEntries() {

    // Get list of checked filter ID's
    var checked = [];
    $('#filterMenu .dropdown-menu i.fa-check-square-o').parent().each(function(){
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

    api_call('logger/get', data=data, renderLogEntries);
}

//------------------------------------------------------------------------------
function renderLogEntries(resp) {

    var filter_tags = ['sms_msg'];
    var badges = {
        'DEBUG': {'class': 'btn-outline-secondary', 'text':'DEBUG'},
        'INFO': {'class': 'btn-outline-primary', 'text':'&nbsp;&nbsp;INFO&nbsp;&nbsp;'},
        'WARNING': {'class': 'btn-outline-warning', 'text':'WARNING'},
        'ERROR': {'class': 'btn-outline-danger', 'text':'ERROR'},
        'EXCEPTION': {'class':'btn-outline-danger', 'text':'EXCEPTION'}
    };

    console.log("%s. %s events returned", resp['status'], resp['data'].length);
    var logs = resp['data'];
    $('#recnt_list').empty();

    for(var i=0; i<logs.length; i++) {
        if(logs[i]['tag'] && filter_tags.indexOf(logs[i]['tag']) > -1)
                continue;

        $item = $('#event_item').clone();//.prop('id', 'list_grp_'+String(i));
        $item.find('#event_msg').html(logs[i]['message']);
        $item.find('#event_dt').html(toRelativeDateStr(new Date(
            logs[i]['timestamp']['$date'])));

        $item.prop('hidden', false);

        if(logs[i]['duration'])
            $item.find('#elapsed').html(logs[i]['duration']);
        else if(logs[i]['elapsed'])
            $item.find('#elapsed').html(logs[i]['elapsed']);
        else
            $item.find('#elapsed').html('None');

        logs[i]['timestamp'] = new Date(logs[i]['timestamp']['$date'])
            .strftime('%b %d at %I:%M %p');
        delete logs[i]['asctime'];

        var $json = $item.find('#json-container');
        // Write log data to collapsible JSON widget
        $json.jsonview(logs[i]);

        var $badge = $item.find('#badge');
        $badge.addClass(badges[logs[i]['level']]['class']);
        $badge.html(badges[logs[i]['level']]['text']);

        $('#recnt_list').append($item);

        $badge.click(function(e){ 
            var $par = $(this).closest('#event_item');
            var $row = $par.find('#log-data');
            if($row.prop('hidden') == true) {
                $row.prop('hidden', false);
                $row.find('.expanded.collapsed:first').trigger('click');
            }
            else {
                $row.find('.expanded:first').trigger('click');
                setTimeout(function() {
                    $row.prop('hidden', true);
                },
                150);
            }
        });

        // Collapse everything 
        $json.find('.expanded').trigger('click'); //slice(1).trigger('click');


    }
}
