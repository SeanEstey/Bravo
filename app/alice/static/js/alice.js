/* alice.js */

//------------------------------------------------------------------------------
function initAlicePane() {
    /* Setup event handlers and pull chatlog data */

    $('#chat_modal').find('#send_sms').click(sendMessage);
    api_call('alice/chatlogs', data={}, renderChatCards);

    $modal = $('#chat_modal');
    $modal.find('input[name="mute"]').click(function() {
        
        api_call(
            'alice/toggle_reply_mute',
            data = {
                'mobile': $modal.data('mobile'),
                'enabled': JSON.parse($(this).prop('checked'))
            },
            function(response) {
                console.log(response['data']);
            });
    });

}

//------------------------------------------------------------------------------
function sendMessage(e) {

    api_call(
        'alice/compose',
        data = {
            'body': $modal.find('input[name="msg"]').val(),
            'to': $modal.data('mobile'),
            'mute': $modal.find('input[name="mute"]').prop('checked'),
            'acct_id': $modal.data('acct_id')
        },

        function(response) {
            console.log('response: ' + JSON.stringify(response));

            if(response['status'] == 'success') {
                appendMsgRow(
                    $('#chat_modal input').val(),
                    new Date(),
                    'out');
                $('#chat_modal input').val('');
            }
        }
    );
}

//------------------------------------------------------------------------------
function renderChatCards(resp){
    /* Render list-items displaying abbreviated user chat data.
     * Clicking on list-items shows a Modal dialog with full chat data.
     */

    console.log("%s chats (%s)", resp['data'].length, resp['status']);
    alice_pane_init = true;
    $('#convo_list').empty();

    for(var i=0; i<resp['data'].length; i++) {
        var chat = resp['data'][i];
        if(chat['messages'].length < 2)
            continue;

        var title = chat['account'] ? chat['account']['name'] : 'Unregistered User (' + chat['mobile'] + ')';
        var id = "item_" + String(i);
        var last_msg_text = '';
        var last_msg_date = '';

        for(var j=chat['messages'].length-1; j>=0; j--) {
            if(chat['messages'][j]['direction'] == 'in') {
                last_msg_text = chat['messages'][j]['message'];
                last_msg_date = new Date(chat['messages'][j]['timestamp']['$date'])
                    .strftime("%b %d at %I:%M%p");
                break;
            }
        }

        $chat_item = $('#chat_item').clone().prop('id', 'item_'+String(i));
        $chat_item.find('.card-title').html(title);
        $chat_item.find('#last_msg').html(last_msg_text);
        $chat_item.find('#msg_date').html(last_msg_date);
        $chat_item.find('#n_msg').html(chat['messages'].length);
        $chat_item.prop('hidden', false);
        $chat_item.click(showChatModal);
        $chat_item.data("details", chat);
        $('#convo_list').append($chat_item);
    }
}

//------------------------------------------------------------------------------
function appendMsgRow(body, date, direction) {

    var color = {"out":"text-primary", "in":"text-success"};

    $td_dt = $('<td nowrap class="chatlog-dt text-muted"></td>');
    $td_dt.html(date.strftime("%b %d: %I:%M%p"));

    $td_msg = $('<td class="chatlog-msg text-muted"></td>');
    $td_msg.html(body);

    $tr = $('<tr></tr>');
    $tr.append($td_dt).append($td_msg);

    $chatlog = $('#chatlog');
    $chatlog.append($tr);

    // Scroll to bottom of table
    $chatlog.scrollTop($chatlog[0].scrollHeight);
}

//------------------------------------------------------------------------------
function showChatModal(e) {

    e.preventDefault();
    var chat = $(this).data('details');
    var name = chat['account'] ? chat['account']['name'] : 'Unregistered User';
    if(chat['account'])
        var acct_id = chat['account']['id'];
    else
        var acct_id = "";

    $chatlog = $('#chatlog');
    $chatlog.empty();

    for(var i=0; i<chat['messages'].length; i++) {
        var msg_data = chat['messages'][i];
        appendMsgRow(
            msg_data['message'],
            new Date(msg_data['timestamp']['$date']),
            msg_data['direction']);
    }

    $modal = $('#chat_modal');
    $modal.on('shown.bs.modal', function() {
        $('#chatlog').scrollTop($('#chatlog')[0].scrollHeight);
    })
    $modal.data('mobile', chat['mobile']);
    $modal.data('acct_id', acct_id);
    $modal.find('.modal-title').text(name+ ' (' +chat['mobile']+ ')');
    $modal.find('.modal-footer .btn-primary').unbind('click');
    $modal.find('.modal-footer .btn-primary').off('click');
    $modal.find('input[name="mute"]').prop('checked', false);
    $modal.find('#f_acct_id').html("<a href="+window.location.origin+"/accounts?aid="+acct_id+">Acct ID " + acct_id+"</a>");
    $modal.modal('show');
}
