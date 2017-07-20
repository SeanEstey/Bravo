/* search_bar.js */

dropdown = false;
dd_matches = [];
query_val = "";

//------------------------------------------------------------------------------
function initSearchBar() {

    $('.dropdown-menu').width($('#search_input').width());

    $('#search_input').keypress(function (e) {
        if (e.which == 13) {
            var acct_id = $('#search_input').val();
            console.log('Submitting search for "'+acct_id+'"');
            window.location = location.origin + '/accounts?aid='+acct_id;
            return false;
        }
    });

    $('#search').click(function() {
       var acct_id = $('#search_input').val();
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
                var account = dd_matches[i]['account'];
                var href = location.origin + '/accounts?aid='+account['id'];
                var $a = $('<a class="dropdown-item" id="'+i+'" href="'+href+'">'+account['name']+'</a>');
                $('.dropdown-menu').append($a);
            }
        }
    );
}
