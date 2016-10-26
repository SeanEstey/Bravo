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

//------------------------------------------------------------------------------
function showDialog($element, msg, _title, _buttons) {
		/* Error/confirmation dialog UI for all views */

		if(typeof(_buttons) === 'undefined') {
				_buttons = [{ 
					text: "Sorry, I'll fix it", 
					click: function() { $( this ).dialog( "close" ); }
				}];
		}

		if(typeof(_title) === 'undefined') {
			_title = 'What have you done??'
		}

		var dialog_style = { 
			modal: true,
			title: _title,
			dialogClass: 'ui-dialog-osx',
			width: 500,
			height: 'auto',
			buttons: _buttons,
			show: { effect: 'fade', duration:150},
			hide: { effect: 'fade', duration:150}
		};
		
		// MUST have a <p> element for the msg
		$element.find($('p')).html(msg);
		$element.dialog(dialog_style);
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
    var btn = $("<button id='"+btn_id+"' class='btn "+style+" admin'>"+caption+"</button>");

    $('#'+pane_id).append(btn);

    if(data) {
			for(var key in data)	{
				$('#'+btn_id).data(key, data[key]);
			}
    }

    return btn;
}
