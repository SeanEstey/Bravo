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
		});
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

//------------------------------------------------------------------------------
function bannerMsg(msg, type, duration=7500) {
		var $banner = $('.status-banner');

		if(!$banner)
				return false;
		
		if(type == 'info')
			$banner.css('background-color', '#CDE6CD'); 
		else if(type == 'error')
			$banner.css('background-color', '#FFCCCC'); 

		$banner.css('visibility', 'visible');
		$banner.css('opacity', 0);

		$banner.html('<span>' + msg + '</span>');
		$banner.clearQueue();

		$banner.fadeTo('slow', 1);

		if(type == 'info')
				$banner.delay(duration);
		else if(type == 'error')
				$banner.delay(10000);
	
		$banner.fadeTo('slow', 0);
}

//------------------------------------------------------------------------------
function addAdminPanelBtn(pane_id, btn_id, caption, style='btn-info', data=false) {
    var btn = $("<button id='"+btn_id+"' class='btn "+style+" admin'>"+caption+"</button>");

    if(data) {
      btn.data(data);
    }

    $('#'+pane_id).append(btn);

    return btn;
}
