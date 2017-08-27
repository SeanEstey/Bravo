/* analytics.js */

giftData = [];  // Raw gift data (large dataset)
seriesData = {}; // Ordered, totalled dataset (keys==date)
chartData = [];
giftSum = 0;
chart = null;
t1 = new Date();

//-----------------------------------------------------------------------------
function analyticsInit() {

    $('.input-daterange input').each(function() {
        $(this).datepicker({
            format: 'mm/dd/yyyy',
            clearBtn: true,
            autoclose: true,
            todayHighlight: true,
        });
    });

    $('.input-daterange input').change(function() {
        console.log('val='+$(this).find('input').val());

        if($('#end-date').val() && $('#start-date').val())
            $('#analyze').prop('disabled',false);
        else
            $('#analyze').prop('disabled',true);
    });

    $('#start-btn').click(function() {
        var $input = $('#start-date');
        var n = $('.datepicker');

        if(n.length == 0)
            $input.datepicker('show');
        else
            $input.datepicker('hide');
    });

    $('#end-btn').click(function() {
        var $input = $('#end-date');
        var n = $('.datepicker');

        if(n.length == 0)
            $input.datepicker('show');
        else
            $input.datepicker('hide');
    });

    //$('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').first().remove(); //prop('id','top-alert');

    $('#title').html(new Date().strftime("%B %Y Gifts"));

    socket = io.connect('https://' + document.domain + ':' + location.port);
    socket.on('gift_data', receiveBatch);
    socket.on('connect', function(){
        console.log('socket.io connection live.');
    });
    $('#analyze').click(function() {
        requestGifts($('#start-date').val(), $('#end-date').val());
    });
}

//-----------------------------------------------------------------------------
function requestGifts(start_d, end_d) {
    /* Socket.io connection established. Now stream gift data for processing. */

    giftData = [];
    seriesData = {};
    chartData = [];
    giftSum = 0;
    var start_date = new Date(start_d);
    var end_date = new Date(end_d);
    var title = format('Gift Analysis for past %s', toRelativeDateStr(start_date)).toTitleCase();
    $('#title').html(title.slice(0,title.length-4));
    $('.chart').prop('hidden',true);
    $('.loading').prop('hidden',false);

    alertMsg("Analyzing gift data...", "success");

    api_call(
        'gifts/get',
        data={
            'start':Number((start_date.getTime()/1000).toFixed(0)),
            'end':Number((end_date.getTime()/1000).toFixed(0))
        },
        function(response) {
            if(response['status'] == 'success') {
                console.log('gifts/get completed');
            }
            else {
                alertMsg("Error retrieving gift data!", "danger");
            }
    });
}

//------------------------------------------------------------------------------
function receiveBatch(gifts) {
    
    if(gifts.length == 0) {
        var msg = format('%s gifts analyzed successfully.', giftData.length);
        alertMsg(msg, "success", 30000);
        console.log(format('%s [%sms]', msg, getElapsedTime(t1)));
        renderChart();
        return;
    }

    giftData = giftData.concat(gifts);

    // Update dataset
    for(var i=0; i<gifts.length; i++) {
        var gift = gifts[i];
        var dt = new Date(gift['timestamp']);
        var date = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
        var datestamp = date.getTime();

        if(seriesData.hasOwnProperty(datestamp)) {
            seriesData[datestamp]['value'] += gift['amount'];
        }
        else {
            seriesData[datestamp] = {
                'date': date.strftime("%b %d"),
                'label': date.strftime("%b %d"),
                'value': gift['amount']
            }
        }
        giftSum += gift['amount'];
    }

    renderChart();

    console.log(format('+%s series data', gifts.length));
}

//------------------------------------------------------------------------------
function renderChart() {

    var tDraw = new Date();

    if(giftData.length == 0) {
        $('.chart').addClass('d-flex');
        $('.chart').css('align-items', 'center');
        $('.chart').append($('<h4 class="mx-auto">No Gifts</h4>'));
        return;
    }

    $('.loading').prop('hidden',true);
    $('.chart').prop('hidden',false);

    chartData = [];
    var datestamps = Object.keys(seriesData).sort();

    for(var i=0; i<datestamps.length; i++) {
        if(seriesData.hasOwnProperty(datestamps[i]))
            chartData.push(seriesData[datestamps[i]]);
    }

    // Initial render
    if(!chart) {
        chart = drawMorrisChart('chart', chartData, 'date', ['value'], true, false, 'x', 5);
        console.log(format('Chart drawn [%sms]', getElapsedTime(tDraw)));
    }
    // Re-render w/ added series data
    else {
        chart.setData(chartData);
        chart.redraw();
        console.log(format('Chart redrawn [%sms]', getElapsedTime(tDraw)));
    }

    var n_days = Object.keys(seriesData).length;
    var gift_avg = (giftSum/n_days).toFixed(0);
    $('#summary').html(format('Days: %s, Total: $%s, Average: $%s', n_days, giftSum.toFixed(0), gift_avg));
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
}
