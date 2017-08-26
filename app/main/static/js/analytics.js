/* analytics.js */

gAcctId = null;
gAcct = null;
gGeolocation = null;
gMobile = null;

//-----------------------------------------------------------------------------
function analyticsInit() {

    $(function () {
      $('[data-toggle="tooltip"]').tooltip();
    })

    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').first().prop('id','top-alert');

    $('#title').html(new Date().strftime("%B %Y Gifts"));

    var today = new Date();
    var mnth_st = new Date(today.getFullYear(), today.getMonth(), 1);
    api_call(
        'gifts/get',
        data={
            'start':Number((mnth_st.getTime()/1000).toFixed(0)),
            'end':Number((today.getTime()/1000).toFixed(0))
        },
        displayGraph);
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
    return;                
}

//------------------------------------------------------------------------------
function displayGraph(response) {
    /*Aggregate gift data and draw morris.js bar graph.
       '1': {'amount':839.25,'date':'Jul-1-2017'},
       '2': {'amount':393.2, 'date':'Jul-2-2017'},
       ...
       '31': {'amount':393.9, 'date':'Jul-31-2017'}
    @gifts: eTapestry Gift Objects. gift['date'] = {'$date':1279391000} (timestamp)
    */

    if(response['status'] != 'success' || ! response['data'] instanceof Array) {
        $('.chart-panel .panel-body').addClass("text-center").html("NO DONATION DATA FOUND");
        return;
    }

    console.log(format('Retrieved %s gifts', response['data'].length));

    var gifts = response['data'];
    var n_gifts = gifts.length;
    var total = 0;
    var chart_data = [];
    var grp_data = {};

    for(var i=0; i<gifts.length; i++) {
        var gift = gifts[i];
        var date = new Date(gift['date']['$date']);
        var cal_day = date.getDate();

        if(grp_data.hasOwnProperty(cal_day)) {
            grp_data[cal_day]['amount'] += gift['amount'];
            
        }
        else {
            grp_data[cal_day] = {
                'date': date.strftime("%b %d"),//toDateString(),
                'amount': gift['amount']
            }
        }
        total += gift['amount'];
    }

    for(var i=0; i<31; i++) {
        var day_key = String(i+1);

        if(grp_data.hasOwnProperty(day_key)) {
            var data = grp_data[day_key];
            chart_data.push({
                'date': data['date'],
                'value': data['amount'],
                'label': data['date']
            });
        }
    }

    total = total.toFixed(0);
    
    /*if(n_gifts > 0)
        var avg_gift = (total/n_gifts).toFixed(2);
    else
        var avg_gift = "--";
    */

    $('#sum').html(format('%s Collection Days, $%s Total', Object.keys(grp_data).length, total));
    $('.chart-panel .loading').hide();

    if(gifts.length > 0) {
        $('.chart').prop('hidden',false);
        drawMorrisChart(
            'chart', chart_data, 'date', ['value'],
            true, false, 'x', 5);
    }
    else {
        $('.chart').prop('hidden',false);
        $('.chart').addClass('d-flex');
        $('.chart').css('align-items', 'center');
        var $no_gifts = $('<h4 class="mx-auto">No Gifts</h4>');
        $('.chart').append($no_gifts);
    }

    $('#timeline').prop('hidden',false);
}

//-----------------------------------------------------------------------------
function displayAcctData(acct) {

    /* CHART PANEL */
    var dv_signup = getDV('Signup Date', acct);
    if(dv_signup)
        $('#joined-d').html(dv_signup.strftime("%b %Y").toUpperCase());

}

