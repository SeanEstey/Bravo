/r* analytics.js */

dataSets = ['gift-revenue', 'n-donor-trend'];
giftData = [];  // Raw gift data (large dataset)
seriesData = {}; // Ordered, totalled dataset (keys==date)
chartData = [];
start_dt = null;
end_dt = null;
giftSum = 0;
seriesGroupings = ['day', 'month', 'year'];
groupBy = 'day'; // default
barChart = null;
t1 = new Date();
chartWidth = null;
angle = 360;


//-----------------------------------------------------------------------------
function initCanvas() {

    $cv = $('#cv');
    var canvas = document.getElementById('cv');

    // Make canvas coord dimensions match DOM dimensions
    canvas.width = $('.chart').width();
    canvas.height = $('.chart').height();
    $cv.width(canvas.width);
    $cv.height(canvas.height);

    // Create 'loader' layer
    $cv.drawPolygon({
      layer:true,
      name:'loader',
      fillStyle:'rgba(39, 155, 190, 0.5)',
      x:canvas.width/2,
      y:canvas.height/2,
      radius: 50,
      sides: 5,
      concavity: 0.5
    });

    $cv.getLayer('loader').visible = true;
}

//-----------------------------------------------------------------------------
function loopLoaderAnim(){

    var loopDuration = 3000;
    angle = angle *-1;
    var p = $('#cv').getLayer('loader');
    $('#cv').animateLayer(
        'loader',
        {rotate:angle},
        loopDuration,
        loopLoaderAnim
    );
}

//-----------------------------------------------------------------------------
function resizeCanvas() {

    chartWidth = $('.chart').width();

    // Resize canvas coordinate dimensions
    var canvas = document.getElementById('cv');
    canvas.width = chartWidth;

    // Resize DOM canvas dimensions
    $('#cv').width(canvas.width);
    $('#cv').height(canvas.height);

    // Adjust layer positions
    var layers = $('#cv').getLayers();
    for(var i=0; i<layers.length; i++) {
        var layer = layers[i];
        layer.x = canvas.width/2 - layer.width/2;
        if(layer.name == 'title')
            continue;
    }

    $('#cv').drawLayers();
}

//-----------------------------------------------------------------------------
function analyticsInit() {

    chartWidth = $('.chart').width();
    initCanvas();
    $(window).resize(function(e) {
        if($('.chart').width() != chartWidth) {
            resizeCanvas();
        }
    });

    $('#dataset-dd .dropdown-item').click(function() {
        console.log($(this).html());
        $('#dataset-btn').text($(this).html());
    });

    $('.input-daterange input').each(function() {
        $(this).bDatepicker({
            format: 'mm/dd/yyyy',
            clearBtn: true,
            autoclose: true,
            todayHighlight: true,
        });
    });

    $('.input-daterange input').change(function() {
        if($('#end-date').val() && $('#start-date').val())
            $('#analyze').prop('disabled',false);
        else
            $('#analyze').prop('disabled',true);
    });

    $('.input-daterange input').click(toggleDatePicker);
    $('.input-daterange .input-group-addon').click(toggleDatePicker);

    $('.br-alert').first().remove();
    $('#title').html(new Date().strftime("%B %Y Gifts"));

    socket = io.connect('https://' + document.domain + ':' + location.port);
    socket.on('gift_data', updateSeries);
    socket.on('connect', function(){
        console.log('socket.io connection live.');
    });

    $('#analyze').click(function() {
        initGiftAnalysis($('#start-date').val(), $('#end-date').val());
    });

    //$('.analy-title').hide();
    $('#ctrl-panel').collapse('show');
    $('#chart-panel').collapse('show');

    $('div').on('shown.bs.collapse', function() {
        var id = $(this).prop('id');
        if(['chart-panel','res-panel','ctrl-panel'].indexOf(id) > -1) {
            console.log(format('%s expanded', $(this).prop('id')));
            $(this).prev().find('.fa-window-maximize').removeClass('fa-window-maximize').addClass('fa-window-minimize');
            $(this).next().css('border-top','1px solid rgba(106,108,111,0.23)');
        }
    });

    $('div').on('hidden.bs.collapse', function() {
        var id = $(this).prop('id');
        if(['chart-panel','res-panel','ctrl-panel'].indexOf(id) > -1) {
            console.log(format('%s collapsed.', $(this).prop('id')));
            $(this).prev().find('.fa-window-minimize').removeClass('fa-window-minimize').addClass('fa-window-maximize');
            $(this).next().css('border-top','none');
        }
    });
}

//-----------------------------------------------------------------------------
function toggleDatePicker(e) {

    // Clicked on input-group-addon
    if($(this).prop('id') == 'start-btn' || $(this).prop('id') == 'end-btn') {
        var $input = $(this).prev();
        $('.datepicker').length == 0 ? $input.bDatepicker('show') : $input.bDatepicker('hide');
    }
}

//-----------------------------------------------------------------------------
function initGiftAnalysis(start_str, end_str) {
    /* Socket.io connection established. Now stream gift data for processing. */

    t1 = new Date();
    barChart=null;
    giftData = [];
    seriesData = {};
    chartData = [];
    giftSum = 0;

    start_dt = new Date(new Date(start_str).getTime());
    end_dt = new Date(new Date(end_str).getTime());

    var day_ms = 86400000;
    var month_ms = day_ms * 31;
    var year_ms = day_ms * 365;
    var tz_diff = 1000 * 3600 * 6;
    var period_ms = end_dt.getTime()-start_dt.getTime();
    var period_str = '';

    if(period_ms <= month_ms)
        groupBy ='day';
    else if(period_ms > month_ms)
        groupBy = 'month';

    $('.chart svg').remove();
    $('.chart .morris-hover').remove();
    $('#foot-status').text('Requesting data from server');
    //$('.analy-title').hide();
    $('#cv').getLayer('loader').visible = true;
    $('#cv').show();
    loopLoaderAnim();

    var tz_diff = 1000 * 3600 * 6;

    api_call(
        'gifts/get',
        data={
            'start':Number((start_dt.getTime()/1000).toFixed(0)),
            'end':Number(((end_dt.getTime()+tz_diff*2)/1000).toFixed(0))
        },
        function(response) {
            if(response['status'] == 'success') {
                console.log('api gifts/get complete.');
                $('#foot-status').text(format('Done. Rendered %s datapoints in %s seconds.',
                    Sugar.Number.abbr(giftData.length,1), Sugar.Number.abbr(getElapsedTime(t1)/1000,1)));
            }
            else {
                alertMsg("Error retrieving gift data!", "danger");
            }
    });
}

//------------------------------------------------------------------------------
function updateSeries(gifts) {
    /* seriesData stores timestamps in UTC */

    if(gifts.length == 0) {
        var msg = format('%s gifts analyzed successfully.', giftData.length);
        alertMsg(msg, "success", 30000);
        console.log(format('%s [%sms]', msg, getElapsedTime(t1)));
        $('#foot-status').text(format('Done. Rendered %s datapoints in %s seconds.',
            Sugar.Number.abbr(giftData.length,1), Sugar.Number.abbr(getElapsedTime(t1)/1000,1)));
        renderBarChart();
        renderSummary();
        return;
    }

    var tz_diff = 1000 * 3600 * 6;

    giftData = giftData.concat(gifts);

    // Update dataset
    for(var i=0; i<gifts.length; i++) {
        var grp_key = null;
        var date_lbl = null;
        var lbl = null;
        var gift = gifts[i];
        var dt = new Date(gift['timestamp']+tz_diff);

        if(groupBy == 'day') {
            // Use start of day timestamp as grouping key
            grp_key = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
            date_lbl = lbl = dt.strftime("%b %d '%y");
        }
        else if(groupBy == 'month') {
            // Use start of month timestamp as grouping key
            grp_key = new Date(dt.getFullYear(), dt.getMonth(), 1).getTime();
            date_lbl = lbl = dt.strftime("%b '%y");
        }
        else if(groupBy == 'year') {
            console.log('YEAR GROUPING NOT SUPPORTED YET');
            return;
        }

        if(seriesData.hasOwnProperty(grp_key)) {
            if(gift['personaType'] == 'Personal')
                seriesData[grp_key]['res'] += gift['amount'];
            else if(gift['personaType'] == 'Business')
                seriesData[grp_key]['bus'] += gift['amount'];
        }
        else {

            seriesData[grp_key] = {
                'date': date_lbl,
                'personaType': gift['personaType'],
                'label': lbl
            }

            if(gift['personaType'] == 'Personal') {
                seriesData[grp_key]['res'] = gift['amount'];
                seriesData[grp_key]['bus'] = 0;
            }
            else if(gift['personaType'] == 'Business') {
                seriesData[grp_key]['bus'] = gift['amount'];
                seriesData[grp_key]['res'] = 0;
            }
        }
        giftSum += gift['amount'];
    }

    $('.analy-title').show();
    $('.analy-title').text(format('%s donations analyzed.', Sugar.Number.abbr(giftData.length,1)));
}

//------------------------------------------------------------------------------
function renderSummary() {

    var datestamps = Object.keys(seriesData);
    var startd = new Date(Number((datestamps[0])));
    var endd = new Date(Number(datestamps[datestamps.length-1]));

    $('.analy-title').show();
    $('.analy-title').text("Analysis & rendering completed");

    // Display chart title
    setTimeout(function(){
        var to_str = null;
        var period_str = '';

        if(groupBy == 'day') {
            period_str = 'Daily';
            to_str = '%b %d %Y';
        }
        else if(groupBy == 'month') {
            period_str = 'Monthly';
            to_str = '%b %Y';
        }
        else if(groupBy == 'year') {
            to_str = '%Y';
        }
        $('.analy-title').text(format("%s Gift Estimates, %s–%s",  
            period_str, startd.strftime(to_str), endd.strftime(to_str)));
    }, 3000);

    // Show results panel
    var n_groups = Object.keys(seriesData).length;
    $('#total-card').show();
    $('#total-card .admin-stat').html(format('$%s', Sugar.Number.abbr(giftSum,1)));
    $('#avg-card').show();
    $('#avg-card .admin-stat').html(format('$%s', Sugar.Number.abbr(giftSum/n_groups,1)));
    $('#datapoints-card').show();
    $('#datapoints-card .admin-stat').html(format('%s', Sugar.Number.abbr(giftData.length,1)));
}

//------------------------------------------------------------------------------
function renderBarChart() {

    chartData = [];
    var tDraw = new Date();

    if(giftData.length == 0) {
        $('.chart').addClass('d-flex');
        $('.chart').css('align-items', 'center');
        $('.chart').append($('<h4 class="mx-auto">No Gifts</h4>'));
        return;
    }

    var plotKeys = Object.keys(seriesData).sort();

    for(var i=0; i<plotKeys.length; i++) {
        // No decimals
        var k = plotKeys[i];
        seriesData[k]['res'] = Number(seriesData[k]['res'].toFixed(0));
        seriesData[k]['bus'] = Number(seriesData[k]['bus'].toFixed(0));
        chartData.push(seriesData[k]);
    }

    $('#cv').getLayer('loader').visible = false;
    $('#cv').hide();
    $('.chart svg').show();

    // Initial render
    if(!barChart) {
        barChart = drawMorrisBarChart(
            'chart',
            chartData,
            'date',
            ['res','bus'],
            options={'labelTop':true, 'stacked':true, 'padding':25} //'barColors':['#279bbe','red']}
        );

        console.log(format('Chart drawn [%sms]', getElapsedTime(tDraw)));
    }
    // Update w/ added series data
    else {
        barChart.setData(chartData);
        barChart.redraw();
        console.log(format('Chart updated [%sms]', getElapsedTime(tDraw)));
    }
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
}
