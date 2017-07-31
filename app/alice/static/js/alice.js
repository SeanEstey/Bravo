/* alice.js */

chatData = null;

//------------------------------------------------------------------------------
function initAlicePane() {
    /* Setup event handlers and pull chatlog data */

    $('#chat_modal').find('#send_sms').click(sendMessage);

    api_call('alice/chatlogs', data={}, function(response) {
        chatData = response['data'];
        renderChatCards(chatData);
    });

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

    $('#fltr-all').click(function() {
        renderChatCards(filterData('all'));
    });

    $('#fltr-unreg').click(function() {
        renderChatCards(filterData('unregistered'));
    });

    $('#fltr-unread').click(function() {
        renderChatCards(filterData('unread'));
    });
}

//------------------------------------------------------------------------------
function filterData(view) {

    console.log('chatData.length='+chatData.length);
    var data = [];

    for(var i=0; i<chatData.length; i++) {
        var chat = chatData[i];

        if(view == 'unregistered') {
            if(chat['account'])
                continue;
        }

        data.push(chat);
    }
    return data;
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
function renderChatCards(data){
    /* Render list-items displaying abbreviated user chat data.
     * Clicking on list-items shows a Modal dialog with full chat data.
     */

    alice_pane_init = true;
    $('#convo_list').empty();
    var n_cols = 3;

    console.log("%s chats", data.length);

    for(var i=0; i<data.length; i+=n_cols) {
        var $row = $('<div class="row mx-auto my-4"></div>');
        var $col = $('<div class="col-md-12 p-0"></div>'); 
        var $deck = $('<div class="card-deck"></div>');

        for(var j=0; j<n_cols; j++) {
            if(i+j >= data.length)
                break;

            var chat = data[i+j];
            if(chat['messages'].length < 2)
                continue;

            var title = chat['account'] ? chat['account']['name'] : chat['mobile'];
            var id = "item_" + String(i);
            var msg = '';
            var msg_dt = new Date();

            for(var m=chat['messages'].length-1; m>=0; m--) {
                if(chat['messages'][m]['direction'] == 'in') {
                    msg = chat['messages'][m]['message'];
                    msg_dt = new Date(chat['messages'][m]['timestamp']['$date']);
                    break;
                }
            }

            var $card = $('#chat-item').clone().prop('id', 'item_'+String(i+j));
            $card.find('.chat-title').html(title);
            $card.find('#last_msg').html(msg);
            $card.find('#msg_date').html(toRelativeDateStr(msg_dt));
            $card.find('#n_msg').html(chat['messages'].length);
            $card.prop('hidden', false);
            $card.click(showChatModal);
            $card.data("details", chat);
            $deck.append($card);
        }

        $col.append($deck);
        $row.append($col); 
        $('#convo_list').append($row);
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
