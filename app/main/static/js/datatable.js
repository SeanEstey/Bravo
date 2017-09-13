/* datatable.js 
v0.11
*/

fields = [
    {
        column:     { title:'Timestamp' },
        data:       { k:'date', sub_k:'$date' },
        columnDef:  { targets:0, visible:false, searchable:false }
    },
    {
        column:     { title:'Date'+
                            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;',
                      width:"15%" },
        data:       { k:'date', sub_k:'$date', value:function(v){ return new Date(v).strftime('%b %d %Y') } },
        columnDef:  { targets:1, width:"15%" }
    },
    {
        column:     { title:'Block' },
        data:       { k:'block', sub_k:false },
        columnDef:  false
    },
    {
        column:     { title:'Size' },
        data:       { k:'stats', sub_k:'nBlockAccounts' },
        columnDef:  false
    },
    {
        column:     { title:'Skips' },
        data:       { k:'stats', sub_k:'nSkips' },
        columnDef:  false
    },
    {
        column:     { title:'Orders' },
        data:       { k:'stats', sub_k:'nOrders' },
        columnDef:  false
    },
    {
        column:     { title:'Zeros' },
        data:       { k:'stats', sub_k:'nZeros' },
        columnDef:  false
    },
    {
        column:     { title:'Donations' },
        data:       { k:'stats', sub_k:'nDonations' },
        columnDef:  false
    },
    {
        column:     { title:'Collect. Rate' },
        data:       { k:'stats', sub_k:'collectionRate',
                      value:function(v){ return typeof(v)=='number' ? Sugar.Number.format(v*100,1)+'%' : '' } },
        columnDef:  false
    },
    {
        column:     { title:'Estimate' },
        data:       { k:'stats', sub_k:'estimateTotal' },
        columnDef:  { targets:9, render:function(data,type,row){ return data ? '$'+Sugar.Number.format(data,2) : ''; } }
    },
    {
        column:     { title:'Receipt' },
        data:       { k:'stats', sub_k:'receiptTotal' },
        columnDef:  { targets:10, render:function(data,type,row){ return data ? '$'+Sugar.Number.format(data,2) : ''; } }
    },
    {
        column:     { title:'Estimate Avg' },
        data:       { k:'stats', sub_k:'estimateAvg' },
        columnDef:  { targets:11, render:function(data,type,row){ return data ? '$'+Sugar.Number.format(data,2) : ''; } }
    },
    {
        column:     { title:'Estimate Trend' },
        data:       { k:'stats', sub_k:'estimateTrend',
                      value:function(v){ return '$'+Sugar.Number.format(v,2); } },
        columnDef:  false
    },
    {
        column:     { title:'Estimate Margin' },
        data:       { k:'stats', sub_k:'estimateMargin',
                      value:function(v){ return typeof(v)=='number' ? Sugar.Number.format(v*100,1)+'%' : '' } },
        columnDef:  false
    },
    {
        column:     { title:'Status' },
        data:       { k:'routific', sub_k:'status'},
        columnDef:  false
    },
    {
        column:     { title:'Unserved' },
        data:       { k:'routific', sub_k:'nUnserved'},
        columnDef:  false
    },
    {
        column:     { title:'Warnings' },
        data:       { k:'routific', sub_k:'warnings', value:function(v){ return v.length}},
        columnDef:  false
    },
    {
        column:     { title:'Errors' },
        data:       { k:'routific', sub_k:'errors', value:function(v){return v.length}},
        columnDef:  false
    },
    {
        column:     { title:'Depot' },
        data:       { k:'routific', sub_k:'depot', value:function(v){ return v.name? v.name : '' }},
        columnDef:  false
    },
    {
        column:     { title:'Driver' },
        data:       { k:'routific', sub_k:'driver', value:function(v){ return v.name? v.name : '' }},
        columnDef:  false
    },
    {
        column:     { title:'Invoice' },
        data:       { k:'driverInput', sub_k:'invoiceNumber'},
        columnDef:  false
    },
    {
        column:     { title:'Mileage' },
        data:       { k:'driverInput', sub_k:'mileage'},
        columnDef:  false
    },
    {
        column:     { title:'RA' },
        data:       { k:'driverInput', sub_k:'raName'},
        columnDef:  false
    },
    {
        column:     { title:'Vehicle' },
        data:       { k:'driverInput', sub_k:'vehicle' },
        columnDef:  false
    },
    {
        column:     { title:'RA Hrs' },
        data:       { k:'driverInput', sub_k:'raHrs'},
        columnDef:  false
    },
    {
        column:     { title:'Driver Hrs' },
        data:       { k:'driverInput', sub_k:'driverHrs'},
        columnDef:  false
    },
    {
        column:     { title:'Vehicle Inspection' },
        data:       { k:'driverInput', sub_k:'vehicleInspection'},
        columnDef:  { targets:26, visible:false }
    },
    {
        column:     { title:'Notes' },
        data:       { k:'driverInput', sub_k:'notes'},
        columnDef:  { targets:27, visible:false }
    },
    {
        column:     { title:'Cages' },
        data:       { k:'driverInput', sub_k:'nCages'},
        columnDef:  false
    },
    {
        column:     { title:'Total Duration' },
        data:       { k:'routific', sub_k:'totalDuration', value:function(x){ return Sugar.Number.format(x/60,2) } },
        columnDef:  false
    }
];

tbl_id = 'datatable';
tbl_data = [];
data_tag = 'routes_new';
datatable = null;

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

    //console.log(tbl_data);
    return tbl_data;
}



//------------------------------------------------------------------------------
function formatDataOld(resp_data) {

    var data_hdr = [
        "date", "block", "skips", "orders", "zeros", "donors", "estmt", "receipt",
        "collectRate", "estmtMargin", "estmtTrend", "invoice", "tripSched", "mileage",
        "vehicle", "driver", "tripActual", "driverHrs", "cages"
    ];
    var tbl_rows = [];
    var tbl_columns = [{title:'timestamp'}];
    for(var i=0; i<data_hdr.length; i++) {
        tbl_columns.push({title:Sugar.String.titleize(data_hdr[i])});
    }

    // Widen Date column w/ extra space
    tbl_columns[1] = {title:'Date&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'};

    for(var i=0; i<resp_data.length; i++) {
        var fields = resp_data[i];
        var tbl_row = [fields['date']['$date']];
        for(var j=0; j<data_hdr.length; j++) {
            tbl_row.push(fields[data_hdr[j]] || ''); 
        }
        tbl_rows.push(tbl_row);
    }

    return tbl_rows;
}


// New route format
NEW_FORMAT= {
    "_id" : "ObjectId(59b6c77e4da93a19652ee135)",
    "date" : {"$date":1505168551187},
    "block" : "R2F",
    "group" : "wsf",
    "stats" : {
        "nOrders" : 68,
        "receiptTotal" : null,
        "estimateAvg" : null,
        "estimateTotal" : null,
        "collectionRate" : null,
        "receiptAvg" : null,
        "nDropoffs" : 0,
        "nBlockAccounts" : 83,
        "estimateTrend" : null,
        "nZeros" : null,
        "nDonations" : null,
        "nSkips" : null,
        "estimateMargin" : null
    },
    "routific" : {
        "status" : "pending",
        "nUnserved" : null,
        "nOrders" : null,
        "warnings" : [],
        "driver" : {
            "shift_start" : "08:00",
            "name" : "Default"
        },
        "startAddress" : null,
        "postal" : "",
        "orders" : [],
        "errors" : [],
        "endAddress" : null,
        "jobID" : null,
        "travelDuration" : null,
        "depot" : {
            "blocks" : [ 
                "R2L", 
                "R10M", 
                "R1i", 
                "R1K", 
                "R2N", 
                "R3G", 
                "R4M", 
                "R5F", 
                "R5C", 
                "R7M", 
                "R8M", 
                "R9G"
            ],
            "formatted_address" : "10347 73 Ave NW, Edmonton, AB",
            "name" : "Strathcona"
        },
        "totalDuration" : null
    },
    "driverInput" : {
        "invoiceNumber" : null,
        "mileage" : null,
        "raName" : null,
        "driverName" : null,
        "vehicle" : null,
        "raHrs" : null,
        "driverHrs" : null,
        "vehicleInspection" : null,
        "notes" : null,
        "nCages" : null
    }
}
