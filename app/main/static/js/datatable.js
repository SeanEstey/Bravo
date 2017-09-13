/* datatable.js 
v0.11
*/

num_format = Sugar.Number.format;

data_tag = 'routes_new';
tbl_id = 'datatable';
tbl_data = [];
datatable = null;
fields = [
    { column:{ title:'Timetamp' }, columnDef:{ targets:0, visible:false, searchable:false }, data:{ k:'date', sub_k:'$date' } },
    { column:{ title:'Date&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;', width:"15%" },
      columnDef:{ targets:1, width:"15%" }, data:{ k:'date', sub_k:'$date', value:function(v){ return new Date(v).strftime('%b %d %Y') } } },
    { column:{ title:'Block' }, columnDef:false, data:{ k:'block', sub_k:false } },
    { column:{ title:'Size' }, columnDef:false, data:{ k:'stats', sub_k:'nBlockAccounts' } },
    { column:{ title:'Skips' }, columnDef:false, data:{ k:'stats', sub_k:'nSkips' } },
    { column:{ title:'Orders' }, columnDef:false, data:{ k:'stats', sub_k:'nOrders' } },
    { column:{ title:'Zeros' }, columnDef:false, data:{ k:'stats', sub_k:'nZeros' } },
    { column:{ title:'Donations' }, columnDef:false, data:{ k:'stats', sub_k:'nDonations' } },
    { column:{ title:'Collect. Rate' }, columnDef:false, 
      data:{ k:'stats', sub_k:'collectionRate', value:function(v){ return typeof(v)=='number'? num_format(v*100,1)+'%':'' } } },
    { column:{ title:'Estimate' }, data:{ k:'stats', sub_k:'estimateTotal' },
      columnDef:{ targets:9, render:function(data, type, row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Receipt' }, data:{ k:'stats', sub_k:'receiptTotal' },
      columnDef:{ targets:10, render:function(data, type, row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Estimate Avg' }, data:{ k:'stats', sub_k:'estimateAvg' },
      columnDef:{ targets:11, render:function(data,type,row){ return data? '$'+num_format(data,2) :'' } } },
    { column:{ title:'Estimate Trend' }, columnDef:false, data:{ k:'stats', sub_k:'estimateTrend', value:function(v){ return '$'+num_format(v,2) } } },
    { column:{ title:'Estimate Margin' }, columnDef:false,
      data:{ k:'stats', sub_k:'estimateMargin', value:function(v){ return typeof(v)=='number'? num_format(v*100,1)+'%' :'' } } },
    { column:{ title:'Status' }, columnDef:false, data:{ k:'routific', sub_k:'status'} },
    { column:{ title:'Unserved' }, columnDef:false, data:{ k:'routific', sub_k:'nUnserved'} },
    { column:{ title:'Warnings' }, columnDef:false, data:{ k:'routific', sub_k:'warnings', value:function(v){ return v.length }} },
    { column:{ title:'Errors' }, columnDef:false, data:{ k:'routific', sub_k:'errors', value:function(v){ return v.length } } },
    { column:{ title:'Depot' }, columnDef:false, data:{ k:'routific', sub_k:'depot', value:function(v){ return v.name? v.name : ''} } },
    { column:{ title:'Driver' }, columnDef:false, data:{ k:'routific', sub_k:'driver', value:function(v){ return v.name? v.name : ''} } },
    { column:{ title:'Invoice' }, columnDef:false, data:{ k:'driverInput', sub_k:'invoiceNumber'} },
    { column:{ title:'Mileage' }, columnDef:false, data:{ k:'driverInput', sub_k:'mileage'} },
    { column:{ title:'RA' }, columnDef:false, data:{ k:'driverInput', sub_k:'raName'}, },
    { column:{ title:'Vehicle' }, columnDef:false, data:{ k:'driverInput', sub_k:'vehicle' } },
    { column:{ title:'RA Hrs' }, columnDef:false, data:{ k:'driverInput', sub_k:'raHrs'} },
    { column:{ title:'Driver Hrs' }, columnDef:false, data:{ k:'driverInput', sub_k:'driverHrs'} },
    { column:{ title:'Vehicle Inspection' }, columnDef:{ targets:26, visible:false }, data:{ k:'driverInput', sub_k:'vehicleInspection'} },
    { column:{ title:'Notes' }, columnDef:{ targets:27, visible:false }, data:{ k:'driverInput', sub_k:'notes'} },
    { column:{ title:'Cages' }, columnDef:false, data:{ k:'driverInput', sub_k:'nCages'} },
    { column:{ title:'Total Duration' }, columnDef:false, data:{ k:'routific', sub_k:'totalDuration', value:function(x){ return num_format(x/60,2) } } }
];

//------------------------------------------------------------------------------
function initDatatable() {

    api_call(
      'datatable/get',
      data={'tag':data_tag},
      function(response){
          console.log(format('%s routes received.',
            response['data'].length));

          buildDataTable(
            tbl_id,
            fields.map(function(x){ return x.column }),
            formatDataNew(response['data'])
          );

          // Fix stylings
          $('#datatable_wrapper').css('background-color', 'whitesmoke');
          $('#datatable_wrapper').css('border-top-right-radius', '5px');
          $('#datatable_wrapper .row').first().css('padding', '15px');
          $('#datatable_wrapper .row').first().css('border-bottom', '1px solid rgba(0,0,0,0.12)');
          $('#datatable_wrapper .row').last().css('padding', '.5rem 1.0rem');
          $('#datatable_wrapper .row').last().css('border-top', '1px solid rgba(0,0,0,.12)');
          $('#datatable').parent().css('background-color','white');
          $('#datatable').css('border','none');

          console.log(format('Page loaded in %sms.', Sugar.Date.millisecondsAgo(a)));
      });
}

//------------------------------------------------------------------------------
function buildDataTable(id, columns, data ) {

    datatable = $('#'+id).removeAttr('width').DataTable({
        data: data,
        columns: columns,
        order: [[0,'desc']],
        columnDefs: fields.map(function(x){ return x.columnDef ? x.columnDef : false; }),
        fixedColumns: true,
        responsive:false,
        select:false,
        lengthMenu: [[10, 50, 100,-1], [10, 50, 100, "All"]]
    });

    datatable.columns.adjust().draw();
}

//------------------------------------------------------------------------------
function formatDataNew(data) {

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
