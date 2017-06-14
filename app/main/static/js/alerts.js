/* app/main/static/js/alerts.js */

var globalTimeoutId = false;

//------------------------------------------------------------------------------
function alertMsg(msg, level, duration=7500, id=null) {
    /* Display color-coded message across banner below header.
     * @level: 'success', 'info', 'warning', 'danger'
     */

    if(!msg)
        return;
    if(!id)
		var $alert = $('.br-alert');
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

	$alert.removeClass('alert-success')
        .removeClass('alert-info')
        .removeClass('alert-warning')
        .removeClass('alert-danger')
	    .addClass('alert-'+level);

	$alert.html('<span>' + msg + '</span>');
    fixStyling();

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
		var $alert = $('.br-alert');
    else
        var $alert = $('#'+id);
    clearTimeout(globalTimeoutId);
    $alert.fadeTo('slow', 0);
}

//------------------------------------------------------------------------------
function fixStyling() {
    $('.br-alert').css('margin-left', 'auto'); 
    $('.br-alert').css('margin-right', 'auto'); 
}
