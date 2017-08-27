/* analytics.js */

giftData = [];  // Raw gift data (large dataset)
seriesData = {}; // Ordered, totalled dataset (keys==date)
chartData = [];
giftSum = 0;
chart = null;
t1 = new Date();
dataStart = new Date(new Date().getFullYear(), new Date().getMonth()-3, 1);
dataEnd = new Date();

//-----------------------------------------------------------------------------
function analyticsInit() {

    socket = io.connect('https://' + document.domain + ':' + location.port);
    socket.on('gift_data', receiveBatch);
    socket.on('connect', function(){
        console.log('socket.io connection live.');
        requestGifts();
    });
    $('#search_ctnr').prepend($('.br-alert'));
    $('.br-alert').first().prop('id','top-alert');
    $('#title').html(new Date().strftime("%B %Y Gifts"));
}

//-----------------------------------------------------------------------------
function requestGifts() {
    /* Socket.io connection established. Now stream gift data for processing. */

    var title = format('Gift Analysis for past %s', toRelativeDateStr(dataStart)).toTitleCase();
    $('#title').html(title.slice(0,title.length-4));

    alertMsg("Analyzing gift data...", "warning");

    api_call(
        'gifts/get',
        data={
            'start':Number((dataStart.getTime()/1000).toFixed(0)),
            'end':Number((dataEnd.getTime()/1000).toFixed(0))
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
        alertMsg(msg, "success", -1);
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
        $('.chart').prop('hidden',false);
        $('.chart').addClass('d-flex');
        $('.chart').css('align-items', 'center');
        $('.chart').append($('<h4 class="mx-auto">No Gifts</h4>'));
        return;
    }

    chartData = [];
    var datestamps = Object.keys(seriesData).sort();

    for(var i=0; i<datestamps.length; i++) {
        if(seriesData.hasOwnProperty(datestamps[i]))
            chartData.push(seriesData[datestamps[i]]);
    }

    // Initial render
    if(!chart) {
        $('.chart-panel .loading').hide();
        $('.chart').prop('hidden',false);
        $('#timeline').prop('hidden',false);

        chart = drawMorrisChart('chart', chartData, 'date', ['value'], true, false, 'x', 5);
        console.log(format('Chart drawn [%sms]', getElapsedTime(tDraw)));
    }
    // Re-render w/ added series data
    else {
        chart.setData(chartData);
        chart.redraw();
        console.log(format('Chart redrawn [%sms]', getElapsedTime(tDraw)));
    }

    $('#sum').html(format('$%s Total in %s Collection Days', giftSum.toFixed(0), Object.keys(seriesData).length));
    var avg = (giftSum/Object.keys(seriesData).length).toFixed(0);
    $('#avg').html(format('$%s Daily Average', avg));
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
}
