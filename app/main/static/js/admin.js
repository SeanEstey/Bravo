
//------------------------------------------------------------------------------
function init() {
    $('nav-tabs a').click(function (e) {
      e.preventDefault()
        $(this).tab('show')
    })

    $('#settings').html($('div [name="settings_data"]:first').clone());
    $('#settings [name="settings_data"]').attr('hidden', false);
    $('#settings [name="settings_data"]:first').show();
    enableEditableFields();

    $('#receipt_btn').click(function() {
        var rv = api_call('accounts/preview_receipt', null, function(response){
            console.log(response);
        });
        console.log(rv);
    });
}

//------------------------------------------------------------------------------
function enableEditableFields() {
  $('input').each(function() {
      $(this).keyup(function(event) {
          if(event.keyCode == 13){
              var fields = [];

              $(this).parents().each(function() {
                  if($(this).attr('name')) {
                      fields.push($(this).attr('name'));
                  }
              });

              var full_field = '';

              for(var i=fields.length-1; i>=0; i--) {
                full_field += fields[i];
                if(i > 0)
                  full_field += '.';
              }

              console.log(full_field);
              console.log($(this).val());
              
              saveFieldEdit(full_field, $(this).val());

              $(this).blur();
          }
      });

      $(this).blur(function() {
          console.log('blured');
          //saveFieldEdit($cell, $input);
      });
  });
}

//------------------------------------------------------------------------------
function saveFieldEdit(field, value) {
	$.ajax({
		type: 'POST',
		url: $URL_ROOT + 'update_agency_conf',
		data: {'field':field, 'value':value}}
    ).done(function(response) {
		if(response['status'] != 'success') {
			alertMsg(response['status'], 'danger');
		}
		else {
            alertMsg('Edited field successfully', 'success');
		}
	});
}
