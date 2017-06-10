/* alice.js */

//------------------------------------------------------------------------------
function initAlicePane() {
    /* Setup event handlers and pull chatlog data */

    if(alice_pane_init)
        return;
    else {
        $('#chat_modal').find('#send_sms').click(sendMessage);
        api_call('alice/chatlogs', data={}, renderChatCards);
    }
}

//------------------------------------------------------------------------------
function sendMessage(e) {

    api_call(
        'alice/compose',
        data = {
            'body': $modal.find('input').val(),
            'to': $modal.data('mobile')
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
        var title = chat['account'] ? chat['account']['name'] : 'Unregistered User (' + chat['mobile'] + ')';
        var id = "item_" + String(i);
        var last_msg_text = '';
        var last_msg_date = '';

        for(var j=chat['messages'].length-1; j>=0; j--) {
            if(chat['messages'][j]['direction'] == 'in') {
                last_msg_text = chat['messages'][j]['message'];
                last_msg_date = new Date(chat['messages'][j]['timestamp']['$date'])
                    .strftime("%b %d @ %I:%M%p");
                break;
            }
        }

        $card = $(
          '<a href="#" id="'+id+'" style="margin:0.1em; text-decoration:none;" class="justify-content-between">' +
            '<div ' +
                'class="card list-group-item list-group-item-action ' + 
                'style="width:100%" ' +
                'onmouseover="this.style.color=\'#0275d8\'; this.style.background=\'white\'" ' +
                'onmouseout="this.style.color=\'gray\'"> ' +
              '<div class="card-block" style="padding-bottom:0; padding-top:0">' +
                '<h4 style="" class="card-title">'+ title + '</h4>' +
                '<span class="card-text">Last Message: "'+ last_msg_text +'"</span>' +
                '<p class="card-text">'+ last_msg_date +'</p>' +
              '</div>' +
              '<h5><span class="badge badge-default badge-pill">'+chat['messages'].length+'</span></h5>' +
            '</div>' +
          '</a>'
        );

        $card.click(showChatModal);
        $card.data("details", chat);
        $('#convo_list').append($card);
    }
}

//------------------------------------------------------------------------------
function appendMsgRow(body, date, direction) {

    var color = {"out":"text-primary", "in":"text-success"};

    $td_dt = $('<td nowrap class="chatlog-dt text-muted"></td>');
    $td_dt.html(date.strftime("%b %d: %I:%M%p"));

    $td_msg = $('<td class="chatlog-msg '+color[direction]+'"></td>');
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
    $modal.find('.modal-title').text(name+ ' (' +chat['mobile']+ ')');
    $modal.find('.modal-footer .btn-primary').unbind('click');
    $modal.find('.modal-footer .btn-primary').off('click');
    $modal.modal('show');
}
