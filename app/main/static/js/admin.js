
//------------------------------------------------------------------------------
function init() {
    $('nav-tabs a').click(function (e) {
      e.preventDefault()
        $(this).tab('show')
    })

    $('#notify').html($('div [name="notify"]:first').clone());
    $('#scheduler').html($('div [name="scheduler"]:first').clone());
    $('#routing').html($('div [name="routing"]:first').clone());
    $('#etapestry').html($('div [name="etapestry"]:first').clone());
    enableEditableFields()
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
		data: {'field':field, 'value':value}})
	.done(function(response) {
		if(response['status'] != 'success') {
			alertMsg(response['status'], 'danger');
		}
		else {
				alertMsg('Edited field successfully', 'success');
		}
	});
}
