
function init() {
		console.log('Root url: ' + $URL_ROOT);

		$('#app_menu').hide();

		$('#submit_btn').click(function(event) {
			// This line needs to be here for Firefox browsers
			event.preventDefault(event);
			
			var form_data = new FormData($('#myform')[0]);

			$.ajax({
				type: 'POST',
				url: $URL_ROOT + 'login',
				data: form_data,
				contentType: false,
				processData: false,
				dataType: 'json',
				success: loginSuccess,
				fail: loginFailure
			});

		$('body').css('display','block');
}

function loginSuccess(response) {
		console.log(response);

		if(typeof response == 'string')
			response = JSON.parse(response);

		if(response['status'] == 'success') {
			console.log('login success');
			location.href = $URL_ROOT;
		}
		else if(response['status'] == 'error') {
			$('.modal-title').text(response['title']);
			$('.modal-body').html(response['msg']);
			$('#btn-primary').hide();
			$('#mymodal').modal('show');
		}
}

function loginFail(xhr, textStatus, errorThrown) {
		console.log(xhr);
		console.log(textStatus);
		console.log(errorThrown);

		$('.modal-title').text('Error');
		$('.modal-body').html(xhr.responseText);
		$('.btn-primary').hide();
		$('#mymodal').modal('show');
}
