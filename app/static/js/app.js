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
				console.log('resetting alert timer');
				clearTimeout(globalTimeoutId);
				globalTimeoutId = false;
				$alert.stop(true);

				$alert.fadeTo('slow', 0, function() {
					alertMsg(msg, level, duration);
				});
				return;
		}

    if(level == 'success')
        $alert.css('background-color', '#DFF2BF');
		else if(level == 'info')
			  $alert.css('background-color', '#BDE5F8'); 
    else if(level == 'warning')
        $alert.css('background-color', '#FEEFB3');
		else if(level  == 'danger')
			  $alert.css('background-color', '#FFCCCC'); 

		if(level == 'warning' || level == 'danger')
        duration = 10000;

		$alert.html('<span>' + msg + '</span>');

		$alert.fadeTo('slow', 1, function() {
				globalTimeoutId = setTimeout(function() {
						$alert.fadeTo('slow', 0);
						globalTimeoutId = false;
				},
				duration);
		});	
}

//------------------------------------------------------------------------------
function addAdminPanelBtn(pane_id, btn_id, caption, style='btn-primary', data=false) {
    var btn = $("<button style='text-size:14pt;' id='"+btn_id+"' class='btn btn-block "+style+" admin'>"+caption+"</button>");

    $('#'+pane_id).append(btn);

    if(data) {
			for(var key in data)	{
				$('#'+btn_id).data(key, data[key]);
			}
    }

    return btn;
}
