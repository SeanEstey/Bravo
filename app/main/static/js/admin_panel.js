/* app/main/static/js/admin_panel.js */

var flip=0;
var y_offset=0;

function closeAdminPanel() { $('.admin-panel-div').hide(); }

//------------------------------------------------------------------------------
function addAdminPanelBtn(pane_id, btn_id, caption, style='btn-primary', data=false) {

    var btn = $(
      "<button style='opacity:1; text-size:14pt;' id='"+btn_id+"' " +
      "class='btn btn-block "+style+" admin'>"+caption+"</button>");

    $('#'+pane_id).append(btn);

    if(data) {
		for(var key in data)	{
			$('#'+btn_id).data(key, data[key]);
		}
    }
    return btn;
}

//------------------------------------------------------------------------------
function positionAdminPanel() {

	var height = $('#admin').height(); 
	y_offset = (height * -1) + 85;
	$('#admin').css('bottom', y_offset);
	$('#admin').show();
}

//------------------------------------------------------------------------------
function toggleAdminPanelSize() {

	$('#admin_size_btn').toggle(function(){
        var sign = '+';
        if(flip++ % 2 === 0)
            sign = '-';
        var offset_str = String(y_offset*-1) + 'px';
        $("#admin").animate({top: sign + '='+offset_str}, 500);
        $('#admin_size_btn').css('display', 'block');
    });
}

//------------------------------------------------------------------------------
function showAdminServerStatus() {

    api_call('server/properties', null, function(response) {
		response = response['data'];
		var admin_lbl = '';

		if(response['TEST_SERVER']) {
			admin_lbl += 'Server: <b>Test</b>, ';
			document.title = 'Bravo Test (SSL)';
		}
		else
			admin_lbl += 'Server: <b>Deploy</b>, ';

		if(response['SANDBOX_MODE'])
			admin_lbl += 'Mode: <b>Sandbox</b>, ';
		else
			admin_lbl += 'Mode: <b>Live</b>, ';

		if(response['CELERY_BEAT'])
			admin_lbl += 'Scheduler: <b color="green">Enabled</b>';
		else
			admin_lbl += 'Scheduler: <b color="green">Disabled</b>';

		//alertMsg(msg, 'info', 5000);
		$('#admin-msg').html(admin_lbl);
		positionAdminPanel();
	});
}
