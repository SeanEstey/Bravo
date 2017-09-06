/* analytics.js */

dataSets = ['gift-revenue', 'n-donor-trend'];
giftData = [];  // Raw gift data (large dataset)
seriesData = {}; // Ordered, totalled dataset (keys==date)
chartData = [];
giftSum = 0;
seriesGroupings = ['day', 'month', 'year'];
groupBy = 'day'; // default
barChart = null;
t1 = new Date();

//-----------------------------------------------------------------------------
function analyticsInit() {

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

    $('#load-logo').show();
    $('.chart').hide();
    $('#ctrl-panel').collapse('show');
    $('#chart-panel').collapse('show');
    $('#res-panel').collapse('hide');

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

    giftData = [];
    seriesData = {};
    chartData = [];
    giftSum = 0;
    if(barChart != null) {
        $('.chart').empty();
        barChart=null;
    }

    // Reset DOM
    $('#ctrl-panel').collapse('toggle');
    $('#load-logo').hide();
    $('.loading').hide();
    $('.chart').hide();
    $('#load-spinner').prop('hidden',false).show();

    var day_ms = 86400000;
    var month_ms = day_ms * 31;
    var year_ms = day_ms * 365;
    var tz_diff = 1000 * 3600 * 6;
    var start_dt = new Date(new Date(start_str).getTime());
    var end_dt = new Date(new Date(end_str).getTime());
    var period_ms = end_dt.getTime()-start_dt.getTime();
    if(period_ms <= month_ms) {
        groupBy ='day';
        $('#grp_type').html('Daily');
    }
    else if(period_ms > month_ms) { /* && period_ms <= year_ms)*/
        groupBy = 'month';
        $('#grp_type').html('Monthly');
    }
    /*else if(period_ms > year_ms)
        groupBy = 'year';
    */

    $('#foot-status').text('Requesting data from server');

    setTimeout(function() {
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
    },
    500);

    //console.log(format("Series being grouped by %s.", groupBy));
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

            date_lbl = lbl = dt.strftime("%b %d `%y");
        }
        else if(groupBy == 'month') {
            // Use start of month timestamp as grouping key
            grp_key = new Date(dt.getFullYear(), dt.getMonth(), 1).getTime();
            date_lbl = lbl = dt.strftime("%b `%y");
        }
        else if(groupBy == 'year') {
            console.log('YEAR GROUPING NOT SUPPORTED YET');
            return;
        }

        if(seriesData.hasOwnProperty(grp_key)) {
            seriesData[grp_key]['value'] += gift['amount'];
        }
        else {
            seriesData[grp_key] = {
                'date': date_lbl,
                'label': lbl,
                'value': gift['amount']
            }
        }
        giftSum += gift['amount'];
    }

    renderBarChart();
    //console.log(format('+%s series data', gifts.length));
    $('#foot-status').text(format('%s datapoints received.', Sugar.Number.abbr(giftData.length,1)));
}

//------------------------------------------------------------------------------
function renderSummary() {

    var datestamps = Object.keys(seriesData);
    var startd = new Date(Number((datestamps[0])));
    var endd = new Date(Number(datestamps[datestamps.length-1]));

    // Display chart title
    var to_str = null;
    if(groupBy == 'day')
        to_str = '%b %d %Y';
    else if(groupBy == 'month')
        to_str = '%b %Y';
    else if(groupBy == 'year')
        to_str = '%Y';
    $('#title_start_d').html(startd.strftime(to_str));
    $('#title_end_d').html(endd.strftime(to_str));
    $('.analy-title').show();

    // Show results panel
    var n_groups = Object.keys(seriesData).length;
    $('#total-card').show();
    $('#total-card .admin-stat').html(format('$%s', Sugar.Number.abbr(giftSum,1)));
    $('#avg-card').show();
    $('#avg-card .admin-stat').html(format('$%s', Sugar.Number.abbr(giftSum/n_groups,0)));
    $('#res-panel').collapse('toggle');
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
        seriesData[k]['value'] = Number(seriesData[k]['value'].toFixed(0));
        chartData.push(seriesData[k]);
    }

    // Initial render
    if(!barChart) {
        $('.loading').hide();
        $('#load-spinner').prop('hidden',true).hide();
        $('.chart').show();

        barChart = drawMorrisBarChart(
            'chart', chartData, 'date', ['value'], options=
            {'labelTop':true, /*'axes':'x',*/ 'padding':25, 'barColors':['#279bbe']}
        );

        console.log(format('Chart drawn [%sms]', getElapsedTime(tDraw)));
    }
    // Update w/ added series data
    else {
        barChart.setData(chartData);
        barChart.redraw();
        console.log(format('Chart updated [%sms]', getElapsedTime(tDraw)));
    }

    $('rect').css('fill','#279bbe');
}

//------------------------------------------------------------------------------
function displayError(msg, response) {

    $('#main').prop('hidden', true);
    $('#error').prop('hidden', false);
    $('#err_alert').prop('hidden', false);
    alertMsg(msg, 'danger', id="err_alert");
}
