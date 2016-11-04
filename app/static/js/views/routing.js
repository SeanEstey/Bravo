
//------------------------------------------------------------------------------
function init() {
		buildAdminPanel();

    $(function() {
        $("td[colspan=12]").find("p").hide();
        $("td[name=warnings]").click(toggleGeocodeWarnings);
    });

		alertMsg('Click on Warnings for each route to view any conflicts resolving addresses', 'info', 15000);
}

//------------------------------------------------------------------------------
function toggleGeocodeWarnings(event) {
    event.stopPropagation();
    var $target = $(event.target);

    if ($target.closest("td").attr("colspan") > 1){
        $target.slideUp();
    } 
    else {
        $target.closest("tr").next().find("p").slideToggle();
    }                    
}

//------------------------------------------------------------------------------
function buildAdminPanel() {
    // dev_mode pane buttons
    $('#admin_pane').hide();

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Debug Mode',
      'btn-primary');

		// Prints Routific job_id to console
    show_debug_info_btn.click(function() {
				$(this).prop('disabled', 'true');

				$('#routing-tbl th:last').after('<th width="10%">DEBUG</th>');

				$('tr[id]').each(function() {
            if(! $(this).attr('id'))
                return;

						var $debug_btn = 
							'<button name="debug-btn" ' +
                      'id="' + $(this).attr('id') + '"' +
											'class="btn btn-warning">Print Debug</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
                $.ajax({
                  context: this,
                  type: 'GET',
                  url: 'https://api.routific.com/jobs/' + $(this).attr('id')
                })
                .done(function(response) {
                    //console.log(JSON.parse(response));
                    console.log(response);
                });

								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Debug</b> buttons prints notification info to console.', 'info');
    });
}
