
function init() {
  enableEditableFields()
}

//------------------------------------------------------------------------------
function enableEditableFields() {

  $('label').each(function() {
    
  });


  $("td [nowrap]").on('click',function() {      
    $cell = $(this);

    // Editable fields are assigned 'name' attribute
    var name = $cell.attr('name');

    //if(!name)
    //  return;

    if($cell.find('input').length > 0)
      return;

    var $input = $cell.find('input');
    $input.width(width);
    $input.css('font-size', '16px');
		$input.focus();

		$input.keyup(function(event) {
				if(event.keyCode == 13){
						saveFieldEdit($cell, $input);
				}
		});
  
    // Save edit to DB when focus lost, remove <input> element 
    $input.blur(function() {
				saveFieldEdit($cell, $input);
    });

  });
}

//------------------------------------------------------------------------------
function saveFieldEdit($cell, $input) {
		$cell.html($input.val());
		var field_name = String($cell.attr('name'));

		console.log(field_name + ' edited');

		var payload = {};
		payload[field_name] = $input.val();

		if($input.val() == '---')
			return;

    /*
		$.ajax({
			type: 'POST',
			url: $URL_ROOT + 'notify/' + $cell.parent().attr('id') + '/edit',
			data: payload
		}).done(function(msg) {
				if(msg != 'OK') {
					alertMsg(msg, 'danger');
					$cell.html(text);
				}
				else {
						alertMsg('Edited field successfully', 'success');
				}
		});
    */

		$input.focus();
}
