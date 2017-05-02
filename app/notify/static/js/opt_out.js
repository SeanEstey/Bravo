/*opt_out.js*/

function opt_out_init() {

    $('#logo_a').addClass('logo-a-center');
    $('#logo_img').addClass('logo-img-lg');
    $('#logo_img').removeClass('logo-img-sm');
    $('.nav').hide();
    $('.alert-banner').css('max-width', '400px');

    if($('form input[name="valid"]').val() == "false") {
        alertMsg("This event has expired", "danger");
        $('form button').prop('disabled', true);
        return;
    }

    $('button').click(function(e) {
        e.preventDefault(); // Firefox browsers

        api_call(
            'notify/accts/optout',
            data=$('form').serialize(),
            function(response){
                console.log(response['status']);
                
                if(response['status'] == 'success') {
                    alertMsg("Success!", "success");

                    $('form button').hide();

                    $('#user_msg').text(
                        "Thank you for opting out of your pick-up. " +
                        "This helps us tremendously in being efficient with our driver resources."
                    );
                }
                else {
                    alertMsg(response['desc'], 'danger');
                }
            });

    });
}

