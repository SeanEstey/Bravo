
//------------------------------------------------------------------------------
function init() {

    $('nav-tabs a').click(function (e){
      e.preventDefault()
        $(this).tab('show')
    })

    $('#settings').html($('div [name="settings_data"]:first').clone());
    $('#settings [name="settings_data"]').attr('hidden', false);
    $('#settings [name="settings_data"]:first').show();
    enableEditableFields();

    $('#receipt_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send Email',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#receipt_form').serialize();

        api_call(
          'accounts/preview_receipt',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          });
    });
    
    $('#sms_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send SMS',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#sms_notific_form').serialize();

        api_call(
          'notify/preview/sms',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          });
    });

    $('#email_notific_btn').click(function(e){
        showModal(
          'mymodal',
          'Preview',
          $('.loader-div').parent().html(),
          'Send Email',
          'Close');
        $('#mymodal').find('.loader-div').show();
        $('#mymodal').find('.loader-div label').text('Generating');
        $('#mymodal').find('.btn.loader').fadeTo('slow', 1);
        $('#mymodal .btn-primary').attr('disabled', true);

        e.preventDefault();
        var data = $('#email_notific_form').serialize();

        api_call(
          'notify/preview/email',
          data, 
          function(response){
              console.log(response['status']);
              $('#mymodal .modal-body').html(response['data']);
          });
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
