/* login.js */

//------------------------------------------------------------------------------
function init_login() {

    $('#logo_a').addClass('logo-a-center');
    $('#logo_img').addClass('logo-img-lg');
    $('#logo_img').removeClass('logo-img-sm');
    $('.nav').hide();
    $('.alert-banner').css('margin-top', '3em'); 
    $('.alert-banner').css('max-width', '400px');

    $('#submit_btn').click(function(e) {
        e.preventDefault(); // Firefox browsers

        var credentials = {
            "username": $('#myform [name="username"]').val(),
            "password": $('#myform [name="password"]').val()
        };

        api_call(
            'user/login',
            data=credentials,
            login_handler
        );
    });
}

//------------------------------------------------------------------------------
function login_handler(response) {

    if(response['status'] == 'success') {
        alertMsg("Logged in successfully", 'success');
        
        location.href = $URL_ROOT + '/notify?status=logged_in';
    }
    else {
        alertMsg(response['responseJSON']['desc'], 'danger', -1);

        $('#myform [name="username"]').val("");
        $('#myform [name="password"]').val("");
    }
}
