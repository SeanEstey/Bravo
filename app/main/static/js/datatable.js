/* datatable.js 
v0.11
*/

num_format = Sugar.Number.format;
data_tag = 'routes_new';
raw_data = null;
tbl_id = 'datatable';
tbl_data = [];
datatable = null;
fields = [
    { column:{ title:'Timetamp' }, columnDef:{ targets:0, visible:false, searchable:false }, data:{ k:'date', sub_k:'$date' } },
    { column:{ title:'Select' }, columnDef:false, data:false },
    { column:{ title:'Date&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;', width:"15%" },
      columnDef:{ targets:2, width:"15%" }, data:{ k:'date', sub_k:'$date', value:function(v){ return new Date(v).strftime('%b %d %Y') } } },
    { column:{ title:'Block' }, columnDef:false, data:{ k:'block', sub_k:false } },
    { column:{ title:'Size' }, columnDef:false, data:{ k:'stats', sub_k:'nBlockAccounts' } },
    { column:{ title:'Skips' }, columnDef:false, data:{ k:'stats', sub_k:'nSkips' } },
    { column:{ title:'Orders' }, columnDef:false, data:{ k:'stats', sub_k:'nOrders' } },
    { column:{ title:'Zeros' }, columnDef:false, data:{ k:'stats', sub_k:'nZeros' } },
    { column:{ title:'Donations' }, columnDef:false, data:{ k:'stats', sub_k:'nDonations' } },
    { column:{ title:'Collect. Rate' }, columnDef:false, 
      data:{ k:'stats', sub_k:'collectionRate', value:function(v){ return typeof(v)=='number'? num_format(v*100,1)+'%':'' } } },
    { column:{ title:'Estimate' }, data:{ k:'stats', sub_k:'estimateTotal' },
      columnDef:{ targets:10, render:function(data, type, row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Receipt' }, data:{ k:'stats', sub_k:'receiptTotal' },
      columnDef:{ targets:11, render:function(data, type, row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Estimate Avg' }, data:{ k:'stats', sub_k:'estimateAvg' },
      columnDef:{ targets:12, render:function(data,type,row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Estimate Trend' }, columnDef:false,
      data:{ k:'stats', sub_k:'estimateTrend', value:function(v){ return v? '$'+num_format(v,2) :'' } } },
    { column:{ title:'Estimate Margin' }, columnDef:false,
      data:{ k:'stats', sub_k:'estimateMargin', value:function(v){ return typeof(v)=='number'? num_format(v*100,1)+'%' :'' } } },
    { column:{ title:'Status' }, columnDef:false, data:{ k:'routific', sub_k:'status'} },
    { column:{ title:'Unserved' }, columnDef:false, data:{ k:'routific', sub_k:'nUnserved'} },
    { column:{ title:'Warnings' }, columnDef:false, data:{ k:'routific', sub_k:'warnings', value:function(v){ return typeof(v) == 'object'? v.length : '' }} },
    { column:{ title:'Errors' }, columnDef:false, data:{ k:'routific', sub_k:'errors', value:function(v){ return typeof(v) == "object"? v.length : '' } } },
    { column:{ title:'Depot' }, columnDef:false, data:{ k:'routific', sub_k:'depot', value:function(v){ return v.name? v.name : ''} } },
    { column:{ title:'Driver' }, columnDef:false, data:{ k:'driverInput', sub_k:'driverName', value:function(v){ return v? v : ''} } },
    { column:{ title:'Invoice' }, columnDef:false, data:{ k:'driverInput', sub_k:'invoiceNumber'} },
    { column:{ title:'Mileage' }, columnDef:false, data:{ k:'driverInput', sub_k:'mileage'} },
    { column:{ title:'RA' }, columnDef:false, data:{ k:'driverInput', sub_k:'raName'}, },
    { column:{ title:'Vehicle' }, columnDef:false, data:{ k:'driverInput', sub_k:'vehicle' } },
    { column:{ title:'RA Hrs' }, columnDef:false, data:{ k:'driverInput', sub_k:'raHrs'} },
    { column:{ title:'Trip Hrs' }, columnDef:false, data:{ k:'driverInput', sub_k:'driverTripHrs'} },
    { column:{ title:'Driver Hrs' }, columnDef:false, data:{ k:'driverInput', sub_k:'driverHrs'} },
    { column:{ title:'Vehicle Inspection' }, columnDef:{ targets:28, visible:false }, data:{ k:'driverInput', sub_k:'vehicleInspection'} },
    { column:{ title:'Notes' }, columnDef:{ targets:29, visible:false }, data:{ k:'driverInput', sub_k:'notes'} },
    { column:{ title:'Cages' }, columnDef:false, data:{ k:'driverInput', sub_k:'nCages'} },
    { column:{ title:'Total Duration' }, columnDef:false, data:{ k:'routific', sub_k:'totalDuration', value:function(x){ return x? num_format(x/60,2) : '' } } }
];

//------------------------------------------------------------------------------
function initDatatable() {

    api_call(
      'datatable/get',
      data={'tag':data_tag},
      function(response){
          console.log(format('%s routes received.',
            response['data'].length));

          raw_data = response['data'];

          buildDataTable(
            tbl_id,
            fields.map(function(x){ return x.column }),
            formatData(filterDates(new Date().clearTime(), null))
          );

          showUpcoming();

          // Fix stylings
          $('#datatable_wrapper').css('background-color', 'whitesmoke');
          $('#datatable_wrapper').css('border-top-right-radius', '5px');
          $('#datatable_wrapper .row').first().css('padding', '15px');
          $('#datatable_wrapper .row').first().css('border-bottom', '1px solid rgba(0,0,0,0.12)');
          $('#datatable_wrapper .row').last().css('padding', '.5rem 1.0rem');
          $('#datatable_wrapper .row').last().css('border-top', '1px solid rgba(0,0,0,.12)');
          $('#datatable').parent().css('background-color','white');
          $('#datatable').css('border','none');
          $('#datatable_length').append($('<button type="text" id="route-btn" class="btn btn-primary my-auto ml-4" disabled>Build Route</button>'));

          console.log(format('Page loaded in %sms.', Sugar.Date.millisecondsAgo(a)));
      });

    // Event handlers
    $('.nav-tabs a').click(function (e){
        e.preventDefault();
        var id = $(this).prop('hash');

        if(id == '#upcoming')
            showUpcoming();
        else if(id == '#historic')
            showHistoric();
    });
}

//------------------------------------------------------------------------------
function showUpcoming() {
    // Flter dates >= today, show/hide appropriate columns

    var today = new Date().clearTime();
    var filtData = filterDates(today, null);
    var titles = fields.map(function(x){return x.column.title});
    var show = ['Status','Unserved','Warnings','Errors'];
    var hide = [
        'Zeros','Donatons','Collect. Rate','Estimate','Receipt','Estimate Avg',
        'Estimate Trend','Estimate Margin','Invoice','Mileage','RA','RA Hrs',
        'Trip Hrs','Driver Hrs','Cages','Vehicle'
    ];
    for(var i=0; i<hide.length; i++)
        datatable.column(titles.indexOf(hide[i])).visible(false);
    for(var i=0; i<show.length; i++)
        datatable.column(titles.indexOf(show[i])).visible(true);

    $('#route-btn').show().prop('disabled',true);
    tbl_data = [];
    datatable.clear();
    datatable.rows.add(formatData(filtData));
    datatable.draw();
}

//------------------------------------------------------------------------------
function showHistoric() {
    // Filter dates < today, show/hide appropriate columns

    var show = [
        'Zeros','Donatons','Collect. Rate','Estimate','Receipt','Estimate Avg',
        'Estimate Trend','Estimate Margin','Invoice','Mileage','RA','RA Hrs',
        'Trip Hrs','Driver Hrs','Cages','Vehicle'
    ];
    var hide = ['Status','Unserved','Warnings','Errors'];
    var titles = fields.map(function(x){return x.column.title});
    for(var i=0; i<show.length; i++)
        datatable.column(titles.indexOf(show[i])).visible(true);
    for(var i=0; i<hide.length; i++)
        datatable.column(titles.indexOf(hide[i])).visible(false);
        
    $('#route-btn').hide();
    tbl_data = [];
    datatable.clear();
    datatable.rows.add(
        formatData(
            filterDates(null, new Date().clearTime())));
    datatable.draw();
}

//------------------------------------------------------------------------------
function filterDates(start, end) {

    var filtered = [];

    for(var i=0; i<raw_data.length; i++) {
        var route = raw_data[i];
        var date = new Date(route['date']['$date']);

        if(start && date < start)
            continue;
        if(end && date > end)
            continue;

        filtered.push(route);
    }

    console.log(format('%s routes filtered between %s to %s',
        filtered.length,
        start ? start.strftime('%b-%d-%Y') : 'anytime',
        end ? end.strftime('%b-%d-%Y') : 'anytime'));

    return filtered;
}


//------------------------------------------------------------------------------
function buildDataTable(id, columns, data ) {

    var $checkb = $(
        '<label class="custom-control custom-checkbox">'+
        '  <input type="checkbox" class="custom-control-input">'+
        ' <span class="custom-control-indicator"></span>'+
        '  <span class="custom-control-description">'+
        '</label>'
    );

    datatable = $('#'+id).removeAttr('width').DataTable({
        data: data,
        columns: columns,
        order: [[0,'desc']],
        columnDefs: fields.map(function(x){ return x.columnDef ? x.columnDef : false; }),
        fixedColumns: true,
        responsive:false,
        select:false,
        lengthMenu: [[10, 50, 100,-1], [10, 50, 100, "All"]],
        "fnCreatedRow" : function (row, data, dataIndex) {
            var $check = $checkb.clone();
            $check.find('input').click(selectRoute);
            $(row).children("td:nth-child(1)").append($check);
        }
    });

    datatable.columns.adjust().draw();
}

//------------------------------------------------------------------------------
function selectRoute() {

    if($(this).prop('checked'))
        $('#route-btn').prop('disabled', false);
    else
        $('#route-btn').prop('disabled', true);
}

//------------------------------------------------------------------------------
function formatData(data) {

    var get = Sugar.Object.get;

    // Convert response data to datatable data format
    for(var i=0; i<data.length; i++) {
        var route = data[i];
        var tbl_row = [];

        for(var j=0; j<fields.length; j++) {
            var k = fields[j]['data']['k'];
            var sub_k = fields[j]['data']['sub_k'];
            var val = '';

            if(!sub_k && get(route, k))
                val = route[k];
            else if(sub_k && get(route[k], sub_k))
                val = route[k][sub_k];

            if(fields[j]['data'].hasOwnProperty('value'))
                val = fields[j]['data']['value'](val);

            tbl_row.push(val);
        }
        tbl_data.push(tbl_row);
    }

    return tbl_data;
}
