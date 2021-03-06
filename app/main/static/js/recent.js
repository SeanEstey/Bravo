/* recent.js */

querytime = null;
page = 0;
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
function clearEntries() {

    $('#recnt_list').empty();
    $('#recnt_list').append($('#spinner').clone().prop('id','spin'));
    $('#spin i').show();
}

//------------------------------------------------------------------------------
function initRecent() {

    $('.br-alert').prop('hidden', true);
    clearEntries();
    requestLogEntries();

    $('#filterMenu .dropdown-item').click(toggleFilter)
        .find('.dropdown-menu').show();

    $('#prev').click(function() {
        if(page > 0) {
            page--;
            clearEntries();
            requestLogEntries();
        }
    });

    $('#next').click(function() {
        page++;
        clearEntries();
        requestLogEntries();
    });
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

    page = 0;
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
    data['page'] = page;

    querytime = new Date(); 

    api_call('logger/get', data=data, renderLogEntries);
}

//------------------------------------------------------------------------------
function renderLogEntries(resp) {

    var ignore_tags = ['sms_msg'];
    var badges = {
        'DEBUG': {
            'head-icon':'fa fa-bug',
            'icon-color':'#5bc0de',
            'head-color':'#5bc0de', //FIXME
            'btn-class':'btn-outline-info',
            'btn-text':'DETAILS'
        },
        'INFO': {
            'head-icon':'fa fa-envira',
            'icon-color':'rgba(2, 117, 216, 0.7)',
            'head-color':'#0275d8',
            'btn-class':'btn-outline-primary',
            'btn-text':'DETAILS'
        },
        'WARNING': {
            'head-icon':'fa fa-exclamation-triangle',
            'icon-color':'#f0ad4e',
            'head-color':'#8a6d3b',
            'btn-class':'btn-outline-warning',
            'btn-text':'DETAILS'
        },
        'ERROR': {
            'head-icon': 'fa fa-fire',
            'icon-color':'#d9534f',
            'head-color':'red', //FIXME
            'btn-class':'btn-outline-danger',
            'btn-text':'DETAILS'
        }
    };

    var logs = resp['data'];
    $('#recnt_list').empty();

    console.log(format("%s events returned, t=%sms", resp['data'].length, Sugar.Date.millisecondsAgo(querytime)));

    $('#start-date').val(new Date(logs[0]['standard']['timestamp']['$date']).strftime("%m/%d/%Y"));
    $('#end-date').val(new Date(logs[logs.length-1]['standard']['timestamp']['$date']).strftime("%m/%d/%Y"));


    for(var i=0; i<logs.length; i++) {
        var std = logs[i]['standard'];
        var extra = logs[i]['extra'];
        
        if(std['tag'] && ignore_tags.indexOf(std['tag']) > -1)
            continue;
        if(extra['function'] == 'get_logs')
            continue;

        $item = $('#event_item_template').clone().prop('id', 'event_item');
        $item.find('#head-icon').addClass(badges[std['level']]['head-icon']);
        $item.find('#head-icon').css('color', badges[std['level']]['icon-color']);
        $item.find('#head-msg').html(std['message']);
        $item.find('#head-msg').css('color', '#6a6c6f');

        var $badge = $item.find('#badge');
        $badge.addClass(badges[std['level']]['btn-class']);
        $badge.html(badges[std['level']]['btn-text']);
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

        //$item.find('#time-spn').css('color', badges[std['level']]['color']);
        //$item.find('#elapse-spn').css('color', badges[std['level']]['color']);
        $item.find('#event_dt').html(
            toRelativeDateStr(new Date(std['timestamp']['$date'])));
        if(std['elapsed'])
            $item.find('#elapsed').html(toElapsedStr(std['elapsed']));
        else
            $item.find('#elapsed').html('None');
        $item.prop('hidden', false);

        // Store data in collapsible JSON widget (json-viewer lib)
        std['timestamp'] = new Date(std['timestamp']['$date'])
            .strftime('%b %d at %I:%M %p');
        var $json = $item.find('#json-container');
        $json.jsonview(logs[i]);

        $('#recnt_list').append($item);

        // Collapse JSON tree 
        $json.find('.expanded').trigger('click'); 
    }
}
