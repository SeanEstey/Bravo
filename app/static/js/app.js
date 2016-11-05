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

//------------------------------------------------------------------------------
function showAdminServerStatus() {
		$.ajax({
			type: 'POST',
			context: this,
			url: $URL_ROOT + 'notify/get_op_stats'
		})
		.done(function(response) {
				var admin_lbl = '';
				var msg = 'Hi ' + response['USER_NAME'] + ' ';

				if(response['TEST_SERVER'])
						admin_lbl += 'Server: <b>Test</b>, ';
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

				alertMsg(msg, 'info', 5000);

				$('#admin-msg').html(admin_lbl);
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
function alertMsg(msg, level, duration=7500) {
    /*  Display color-coded message across banner below header.
    * @level: 'success', 'info', 'warning', 'danger'
    */

		var $alert = $('.alert-banner');

		// Existing alert. Clear its timer, fade it out
		if(globalTimeoutId) {
				clearTimeout(globalTimeoutId);
				globalTimeoutId = false;
				$alert.stop(true);

				$alert.fadeTo('slow', 0, function() {
					alertMsg(msg, level, duration);
				});
				return;
		}

		$alert.removeClass('success').removeClass('info').removeClass('warning').removeClass('danger');
		$alert.addClass(level);

		if(level == 'warning' || level == 'danger')
        duration = 10000;

		$alert.html('<span>' + msg + '</span>');

		$alert.fadeTo('slow', 0.75, function() {
				globalTimeoutId = setTimeout(function() {
						$alert.fadeTo('slow', 0);
						globalTimeoutId = false;
				},
				duration);
		});	
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
