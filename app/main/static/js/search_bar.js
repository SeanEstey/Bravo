/* search_bar.js */

dropdown = false;
dd_matches = [];
query_val = "";

//------------------------------------------------------------------------------
function initSearchBar() {

    //    $('.dropdown-menu').width($('#search_input').width());

    $('#search_input').keypress(function (e) {
        if (e.which == 13) {
            var acct_id = $('#search_input').val();
            if(!acct_id)
                return;
            console.log('Submitting search for "'+acct_id+'"');
            window.location = location.origin + '/accounts?aid='+acct_id;
            return false;
        }
    });

    $('#search').click(function() {
       var acct_id = $('#search_input').val();
       if(!acct_id)
          return;
       window.location = location.origin + '/accounts?aid='+acct_id;
    });

    $('#search_input').keyup(function(e){
        var val = $(this).val();

        if(val != query_val && val.length >= 3) {
            showAutocompleteMatches($(this).val());
        }

        query_val = val;
    });
}

//------------------------------------------------------------------------------
function showAutocompleteMatches(query) {
    
    $input = $('#search_input');

    // If we have a valid query str, register a click to open the dropdown
    if(!$('.dropdown .input-group').hasClass('show')) {
        $('#search_input').trigger('click');
    }

    api_call(
        'accounts/get/autocomplete',
        data={'query':query},
        function(response) {
            dd_matches = response['data'];

            if(!Array.isArray(dd_matches)) {
                console.log('No results returned');
                return;
            }
            if(Array.isArray(dd_matches) && dd_matches.length == 0) {
                console.log('Zero results');
                return;
            }

            console.log('Found ' + dd_matches.length + ' matches.');

            $('.dropdown-menu').empty();

            for(var i=0; i<dd_matches.length; i++) {
                var acct = dd_matches[i]['account'];
                var email = acct['email'] ? format("<%s>",acct['email']) : '';
                var state = getDV('Status', acct);

                var $result = $('#search-item').clone()
                    .prop('id',String(i))
                    .prop('href', format('%s/accounts?aid=%s', location.origin, acct['id']))
                    .prop('hidden',false);

                $result.find('#sr-name').text(acct['name']);
                $result.find('#sr-email').text(email);
                $result.find('#sr-addr').text(acct['address'] || '');

                if(!state || state == 'Cancelled')
                    $result.find('#sr-status').addClass('text-danger');
                else
                    $result.find('#sr-status').addClass('text-success');
                
                $('.dropdown-menu').append($result);
            }
        }
    );
}
