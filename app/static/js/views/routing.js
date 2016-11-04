
//------------------------------------------------------------------------------
function init() {
		alertMsg('Click on Warnings for each route to view any conflicts resolving addresses', 'info', 15000);
		buildAdminPanel();
}

//------------------------------------------------------------------------------
function toggleGeocodeWarnings() {
    function toggleWarnings(event) {
          event.stopPropagation();
          var $target = $(event.target);
          if ( $target.closest("td").attr("colspan") > 1 ) {
              $target.slideUp();
          } else {
              $target.closest("tr").next().find("p").slideToggle();
          }                    
      }
    $(function() {
        $("td[colspan=12]").find("p").hide();
        $("td[name=warnings]").click(toggleWarnings);
    });

}

//------------------------------------------------------------------------------
function buildAdminPanel() {
    // dev_mode pane buttons

    show_debug_info_btn = addAdminPanelBtn(
      'dev_pane',
      'debug_info_btn',
      'Debug Mode',
      'btn-primary');

		// Prints Routific job_id to console
    show_debug_info_btn.click(function() {
				$(this).prop('disabled', 'true');

				$('#notific-table th:last').after('<th>DEBUG</th>');

				$('tr[id]').each(function() {
						var $debug_btn = 
							'<button name="debug-btn" ' +
											'class="btn btn-warning">Print Debug</button>';

						$(this).append('<td>'+$debug_btn+'</td>');

						$(this).find('button[name="debug-btn"]').click(function() {
								alertMsg('Debug data printed to console. ' +
												 'To view console in chrome, type <b>Ctrl+Shift+I</b>.', 
												 'warning', 15000);

								var data = $(this).parent().parent().attr('data-tracking');

								// Try to convert unicode dict str to JSON object
								data = data.replace(/u\'/g, '\'').replace(/\'/g, '\"').replace(/None|False|True/g, '\"\"');

								try {
										console.log(JSON.stringify(JSON.parse(data), null, 4));
								}
								catch(e) {
										console.log('couldnt convert to JSON obj.');
										console.log(data);
								}
						});
				});

				alertMsg('Debug mode enabled. ' +
								 'Clicking <b>Print Debug</b> buttons prints notification info to console.', 'info');
    });
}
