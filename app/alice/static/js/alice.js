/* alice.js */

chatData = null;
activeCard = null;

//------------------------------------------------------------------------------
function initAlicePane() {
    /* Setup event handlers and pull chatlog data */

    loadChats();
    initSocketIO();

    $('#chat_modal').find('#send_sms').click(sendMessage);
    $modal = $('#chat_modal');
    $modal.find('input[name="mute"]').click(function() {
        api_call(
            'alice/toggle_reply_mute',
            data = {
                'mobile': $modal.data('mobile'),
                'enabled': JSON.parse($(this).prop('checked'))
            },
            function(response) {
                $('#status').html('Auto-replies muted for 30 min.');
                console.log(response['data']);
            });
    });

    $('#fltr-all').click(function() {
        renderChatCards(filterData('all'));
    });
    $('#fltr-unreg').click(function() {
        renderChatCards(filterData('unregistered'));
    });
    $('#fltr-read').click(function() {
        renderChatCards(filterData('read'));
    });
    $('#fltr-unread').click(function() {
        renderChatCards(filterData('unread'));
    });
}

//------------------------------------------------------------------------------
function loadChats() {

    api_call('alice/chatlogs', data={}, function(response) {
        chatData = response['data'];
        renderChatCards(chatData);
    });
}

//------------------------------------------------------------------------------
function initSocketIO() {

    socket = io.connect('https://' + document.domain + ':' + location.port);
    socket.on('connect', function(){
        console.log('socket.io connected!');
        socket.on('joined', function(response) {
            console.log(response);
        });
    });
    socket.on('new_message', function(data) {
        console.log('New message!');
        var $modal = $('#chat_modal');
        if($modal.hasClass('show')) {
            console.log('Modal active');
            if(data['mobile'] == $modal.data('mobile')) {
                $('#status').html('Message received.');
                appendMsgRow(data['message'], new Date(), 'in');
            }
        }
        // Refresh chat cards
        loadChats();
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
        else if(view == 'unread') {
            if(chat.hasOwnProperty('unread') && chat['unread'] == false)
                continue;
        }
        else if(view == 'read') {
            if(!chat.hasOwnProperty('unread') || chat['unread'] == true)
                continue;
        }
        data.push(chat);
    }

    $('#filterLbl').html('Showing ' + view.toTitleCase());
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
                $('#status').html('Message delivered.');
                appendMsgRow($('#chat_modal input').val(),new Date(),'out');
                $('#chat_modal input').val('');
            }
    });
}

//------------------------------------------------------------------------------
function renderChatCards(data){
    /* Render list-items displaying abbreviated user chat data.
     * Clicking on list-items shows a Modal dialog with full chat data.
     */

    alice_pane_init = true;
    $('#convo_list').empty();
    var n_cols = 3;

    console.log(format("%s chatlogs received, t=%sms", data.length, Sugar.Date.millisecondsAgo(a)));

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
            var last_user_msg = null;
            var last_msg_dt = new Date(chat['last_message']['$date']);
            var last_user_msg_dt = new Date();

            for(var m=chat['messages'].length-1; m>=0; m--) {
                if(chat['messages'][m]['direction'] == 'in') {
                    last_user_msg = '\"' + chat['messages'][m]['message'] + '\"';
                    last_user_msg_dt = new Date(
                        chat['messages'][m]['timestamp']['$date']);
                    break;
                }
            }

            if(!last_user_msg)
                continue;

            var $card = $('#chat-item').clone().prop('id', 'item_'+String(i+j));
            if(chat.hasOwnProperty('unread') && chat['unread'] == false)
                $card.find('#unread').prop('hidden', true);
            $card.find('.chat-title').html(title);
            $card.find('#last_user_msg').html(last_user_msg);
            $card.find('#last_user_msg_dt').html('Received ' + toRelativeDateStr(last_user_msg_dt));
            $card.find('#last_msg_dt').html('Replied ' + toRelativeDateStr(last_msg_dt));
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
    console.log(format("Loaded in t=%sms.", Sugar.Date.millisecondsAgo(a)));
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

    activeCard = $(this);

    e.preventDefault();
    var chat = $(this).data('details');
    var name = chat['account'] ? chat['account']['name'] : '';

    if(chat['account'])
        var acct_id = chat['account']['id'];
    else
        var acct_id = "";

    var url = format("%s/accounts?aid=%s", window.location.origin, acct_id);

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
    $modal.find('#status').html('');
    $modal.data('mobile', chat['mobile']);
    $modal.data('acct_id', acct_id);
    var $acct_url = $(format("<a style='color:#31b0d5' href=%s>%s</a>", url, name) + format("  <span>(%s)</span>", chat['mobile']));
    $modal.find('.modal-title').html($acct_url);
    $modal.find('.modal-footer .btn-primary').unbind('click');
    $modal.find('.modal-footer .btn-primary').off('click');
    $modal.find('input[name="mute"]').prop('checked', false);
    $modal.find('#f_acct_id').html(
        format("<a href=%s>Acct ID %s</a>", url, acct_id));
    $modal.modal('show');

    if(chat.hasOwnProperty('unread') && chat['unread'] == true) {
        api_call(
            'alice/no_unread',
            data={'mobile':chat['mobile']},
            function(response) {
                $('#status').html('Messages marked as read.');
                activeCard.find('#unread').prop('hidden', true);
                console.log(response['status']);
            });
    }
}
