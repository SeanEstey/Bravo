
//------------------------------------------------------------------------------
function init() {
    $('.nav').hide();

		$('#submit_btn').click(function(event) {
			// This line needs to be here for Firefox browsers
			//event.preventDefault(event);
			
			$.ajax({
				type: 'POST',
				url: $URL_ROOT + '/login',
				data: new FormData($('#myform')[0]),
        contentType: false,
        processData: false,
        dataType: 'json'
      }).done(function(response) {
          console.log('success!!');
          loginSuccess(response);
      })
		});

	//	$('body').css('display','block');
}

//------------------------------------------------------------------------------
function loginSuccess(response) {
    //location.href = $URL_ROOT + '/notify';

    console.log('login success');
		console.log(response);

		if(typeof response == 'string')
			response = JSON.parse(response);

		if(response['status'] == 'success') {
			console.log('login success');
			location.href = $URL_ROOT + '/notify';
		}
		else if(response['status'] == 'error') {
			$('.modal-title').text(response['title']);
			$('.modal-body').html(response['msg']);
			$('#btn-primary').hide();
			$('#mymodal').modal('show');
		}
}

//------------------------------------------------------------------------------
function loginFailure(xhr, textStatus, errorThrown) {
		console.log(xhr);
		console.log(textStatus);
		console.log(errorThrown);

		$('.modal-title').text('Error');
		$('.modal-body').html(xhr.responseText);
		$('.btn-primary').hide();
		$('#mymodal').modal('show');
}
