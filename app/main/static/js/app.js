// GLOBALS
this.colors = {
  'SUCCESS': '#5CB85C',
  'FAILED': '#D9534F',
  'DEFAULT': 'black',
  'IN_PROGRESS': '#337AB7'
};

this.unicode = {
  'UP_ARROW': '&#8593;',
  'DOWN_ARROW': '&#8595;',
  'SPACE': '&#32;'
};


var flip=0;
var y_offset=0;

//------------------------------------------------------------------------------
function positionAdminPanel() {

	var height = $('#admin').height(); 
	y_offset = (height * -1) + 85;
	$('#admin').css('bottom', y_offset);
	$('#admin').show();

	console.log('pos_admin_panel(): admin panel height=' + height + ', y offset=' + y_offset);
}

//------------------------------------------------------------------------------
function toggleAdminPanelSize() {
	$('#admin_size_btn').toggle(
		function() {
			var sign = '+';

			if(flip++ % 2 === 0)
					sign = '-';

			var offset_str = String(y_offset*-1) + 'px';
			$("#admin").animate({top: sign + '='+offset_str}, 500);
			$('#admin_size_btn').css('display', 'block');
		}
	);
}

//------------------------------------------------------------------------------
function showAdminServerStatus() {
    api_call('server/properties', null, function(response) {
		response = response['data'];

		var admin_lbl = '';
		//var msg = 'Hi ' + response['USER_NAME'] + ' ';

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

//------------------------------------------------------------------------------
function api_call(path, data, on_done) {
	$.ajax({
		type: 'POST',
      	data: data,
		url: $URL_ROOT + 'api/' + path})
	.done(function(response){
        on_done(response);
    });
}

//------------------------------------------------------------------------------
function loadTooltip() {

$('[data-toggle="tooltip"]').tooltip();

/*
	$(document).tooltip({
		position: {
			my: 'center bottom-20',
			at: 'center top',
			using: function(position, feedback) {
				$(this).css(position);
				$('<div>')
					.addClass('arrow')
					.addClass(feedback.vertical)
					.addClass(feedback.horizontal)
					.appendTo(this);
			}
		}
	});*/
}

var globalTimeoutId = false;

//------------------------------------------------------------------------------
function alertMsg(msg, level, duration=7500, id=null) {
    /*  Display color-coded message across banner below header.
    * @level: 'success', 'info', 'warning', 'danger'
    */

    if(!id)
		var $alert = $('.alert-banner');
    else
        var $alert = $('#'+id);

	// Existing alert. Clear its timer, fade it out
	if(globalTimeoutId) {
		clearTimeout(globalTimeoutId);
		globalTimeoutId = false;
		$alert.stop(true);

		$alert.fadeTo('slow', 0, function() {
			alertMsg(msg, level, duration, id);
		});
		return;
	}

	$alert.removeClass('success').removeClass('info').removeClass('warning').removeClass('danger');
	$alert.addClass(level);

	//if(duration==7500 && (level == 'warning' || level == 'danger'))
    //    duration = 10000;

	$alert.html('<span>' + msg + '</span>');

	$alert.fadeTo('slow', 0.75, function() {
		if(duration > 0)  {
			globalTimeoutId = setTimeout(function() {
				$alert.fadeTo('slow', 0);
				globalTimeoutId = false;
			},
			duration);
		}
	});
}

//------------------------------------------------------------------------------
function fadeAlert(id=null) {
    if(!id)
		var $alert = $('.alert-banner');
    else
        var $alert = $('#'+id);

    clearTimeout(globalTimeoutId);
    $alert.fadeTo('slow', 0);
}

//------------------------------------------------------------------------------
function showModal(id, title, body, btn_prim_lbl, btn_sec_lbl) {
    $modal = $('#'+id);

    $modal.find('.modal-title').text(title);
    $modal.find('.modal-body').html(body);

    $modal.find('.btn-primary').text(btn_prim_lbl);
    $modal.find('.btn-secondary').text(btn_sec_lbl);

    // clear previous btn event handlers
    $modal.find('.btn-primary').unbind('click');

    $modal.modal('show');
}

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
function closeAdminPanel() {
	$('.admin-panel-div').hide();
}
