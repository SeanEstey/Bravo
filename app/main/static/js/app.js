/* app.js */

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
var globalTimeoutId = false; // for alertMsg
dropdown = false;
dd_matches = [];
query_val = "";

//------------------------------------------------------------------------------
function initSearchBar() {

    //    $('.dropdown-menu').width($('#search_input').width());

    $('#search_input').keypress(function (e) {
        if (e.which == 13) {
            var acct_id = $('#search_input').val();
            if(!acct_id)
                return;
            console.log('Submitting search for "'+acct_id+'"');
            window.location = location.origin + '/accounts?aid='+acct_id;
            return false;
        }
    });

    $('#search').click(function() {
       var acct_id = $('#search_input').val();
       if(!acct_id)
          return;
       window.location = location.origin + '/accounts?aid='+acct_id;
    });

    $('#search_input').keyup(function(e){
        var val = $(this).val();

        if(val != query_val && val.length >= 3) {
            showAutocompleteMatches($(this).val());
        }

        query_val = val;
    });
}

//------------------------------------------------------------------------------
function showAutocompleteMatches(query) {
    
    $input = $('#search_input');

    // If we have a valid query str, register a click to open the dropdown
    if(!$('.dropdown .input-group').hasClass('show')) {
        $('#search_input').trigger('click');
    }

    api_call(
        'accounts/get/autocomplete',
        data={'query':query},
        function(response) {
            dd_matches = response['data'];

            if(!Array.isArray(dd_matches)) {
                console.log('No results returned');
                return;
            }
            if(Array.isArray(dd_matches) && dd_matches.length == 0) {
                console.log('Zero results');
                return;
            }

            console.log('Found ' + dd_matches.length + ' matches.');

            $('.dropdown-menu').empty();

            for(var i=0; i<dd_matches.length; i++) {
                var acct = dd_matches[i]['account'];
                var email = acct['email'] ? format("<%s>",acct['email']) : '';
                var state = getDV('Status', acct);

                var $result = $('#search-item').clone()
                    .prop('id',String(i))
                    .prop('href', format('%s/accounts?aid=%s', location.origin, acct['id']))
                    .prop('hidden',false);

                $result.find('#sr-name').text(acct['name']);
                $result.find('#sr-email').text(email);
                $result.find('#sr-addr').text(acct['address'] || '');

                if(!state || state == 'Cancelled')
                    $result.find('#sr-status').addClass('text-danger');
                else
                    $result.find('#sr-status').addClass('text-success');
                
                $('.dropdown-menu').append($result);
            }
        }
    );
}

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

//------------------------------------------------------------------------------
function showModal(id, title, body, btn_prim_lbl, btn_sec_lbl) {

    $modal = $('#'+id);
    $modal.find('.modal-title').text(title);
    $modal.find('.modal-body').html(body);
    $modal.find('.modal-footer .btn-primary').text(btn_prim_lbl);
    $modal.find('.modal-footer .btn-secondary').text(btn_sec_lbl);
    $modal.find('.modal-footer .btn-primary').unbind('click'); // Clear prev btn handlers
    $modal.find('.modal-footer .btn-primary').off('click'); // Clear prev btn handlers
    $modal.modal('show');
}

//------------------------------------------------------------------------------
function api_call(path, data, on_done) {
    /* Returns: {
     *   "status": ["success", "failed"],
     *   "data": <str/int/object/array>
     * }
     */
    
    //console.log('API call "%s", data=%s', path, JSON.stringify(data));

	$.ajax({
		type: 'POST',
      	data: data,
		url: $URL_ROOT + 'api/' + path})
	.done(function(response){
        on_done(response);
    })
    .fail(function(response){
        on_done(response)});
}

//------------------------------------------------------------------------------
function loadTooltip() { $('[data-toggle="tooltip"]').tooltip(); }

/* Etapestry */

function getPhone(type, acct) {

    var phones = acct['phones'];

    if(!phones)
        return null;

    for(var i=0; i<phones.length; i++) {
        if(phones[i]['type'] == type)
            return phones[i]['number'];
    }

    return null;
}

function getDV(name, acct) {

    var multis = [];
    var isMulti = false;

    var dv = acct['accountDefinedValues'];

    if(!dv)
        return null;

    for(var i=0; i<dv.length; i++) {

        if(dv[i]['fieldName'] != name)
            continue

        if(dv[i]['displayType'] == 2) {
            isMulti = true;
            multis.push(dv[i]['value']);
            continue;
        }

        if(dv[i]['dataType'] == 1) {
            var parts = dv[i]['value'].split('/');
            return new Date(format("%s/%s/%s",parts[1],parts[0],parts[2]));
        }

        return dv[i]['value'];
    }

    return isMulti ? multis.join(", ") : null;
}
