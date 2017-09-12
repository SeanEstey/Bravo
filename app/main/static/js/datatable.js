/* datatable.js 
v0.11
*/

data_tag = 'routes_new';
tbl_id = 'datatable';
tbl_columns = [
    {title:'Timestamp', key:'date', subkey:'$date'},
    {title:'Date', key:'date', subkey:'$date', value:function(v){ return new Date(v).strftime('%b %d %Y') }},
    {title:'Block', key:'block', subkey:false},
    {title:'Size', key:'stats', subkey:'nBlockAccounts'},
    {title:'Skips', key:'stats', subkey:'nSkips'},
    {title:'Orders', key:'stats', subkey:'nOrders'},
    {title:'Zeros', key:'stats', subkey:'nZeros'},
    {title:'Donations', key:'stats', subkey:'nDonations'},
    {title:'Estimate', key:'stats', subkey:'estimateTotal'},
    {title:'Receipt', key:'stats', subkey:'receiptTotal'},
    {title:'Estimate Avg', key:'stats', subkey:'estimateAvg'},
    {title:'Estimate Trend', key:'stats', subkey:'estimateTrend'},
    {title:'Estimate Margin', key:'stats', subkey:'estimateMargin'},
    {title:'Receipt', key:'stats', subkey:'receiptTotal'},
    {title:'Status', key:'routific', subkey:'status'},
    {title:'Unserved', key:'routific', subkey:'nUnserved'},
    {title:'Warnings', key:'routific', subkey:'warnings', value:function(v){ return v.length}},
    {title:'Errors', key:'routific', subkey:'errors', value:function(v){return v.length}},
    {title:'Depot', key:'routific', subkey:'depot', value:function(v){return v.name}},
    {title:'Driver', key:'routific', subkey:'driver', value:function(v){return v.name}},
    {title:'Invoice', key:'driverInput', subkey:'invoiceNumber'},
    {title:'Mileage', key:'driverInput', subkey:'mileage'},
    {title:'RA', key:'driverInput', subkey:'raName'},
    {title:'Vehicle', key:'driverInput', subkey:'vehicle'},
    {title:'RA Hrs', key:'driverInput', subkey:'raHrs'},
    {title:'Driver Hrs', key:'driverInput', subkey:'driverHrs'},
    {title:'Vehicle Inspection', key:'driverInput', subkey:'vehicleInspection'},
    {title:'Notes', key:'driverInput', subkey:'notes'},
    {title:'Cages', key:'driverInput', subkey:'nCages'},
];
tbl_data = [];

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
            tbl_columns.map(function(x){ return {title:x.title}}),
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
function formatDataNew(data) {

    var get = Sugar.Object.get;

    // Convert response data to datatable data format
    for(var i=0; i<data.length; i++) {
        var route = data[i];
        var tbl_row = [];

        for(var j=0; j<tbl_columns.length; j++) {
            var k = tbl_columns[j]['key'];
            var sub_k = tbl_columns[j]['subkey'];
            var val = '';

            if(!sub_k && get(route, k))
                val = route[k];
            else if(sub_k && get(route[k], sub_k))
                val = route[k][sub_k];

            if(tbl_columns[j].hasOwnProperty('value'))
                val = tbl_columns[j]['value'](val);

            tbl_row.push(val);
        }
        tbl_data.push(tbl_row);
    }

    //console.log(tbl_data);
    return tbl_data;
}

//------------------------------------------------------------------------------
function buildDataTable(id, columns, data ) {

    var table = $('#'+id).removeAttr('width').DataTable({
        data: data,
        columns: columns,
        order: [[0,'desc']],
        columnDefs: [
            {
                "targets":0, // Timestamp
                "visible":false,
                "searchable":false
            },
            {
                "targets":columns.indexOf('Date')+1,
                "width":100
            },
            {
                "targets":[columns.indexOf('Receipt')+1, columns.indexOf('Estimate')+1],
                "render": function(data, type, row) { return data ? '$'+Sugar.Number.format(data,2) : '';}
            },
            /*{
                'targets':[columns.indexOf('Collection Rate')+1, columns.indexOf('Estimate Margin')+1],
                'render':function(data,type,row){ return typeof(data)=='number' ? Sugar.Number.format(data*100,1)+'%' : '';}
            },
            {
                'targets':columns.indexOf('Estimate Trend')+1,
                'render':function(data,type,row){ return data ? '$'+Sugar.Number.format(data,2) : '';}
            },
            {
                'targets':columns.indexOf('Trip Scheduled')+1,
                'render':function(data,type,row){ return data ? Sugar.Number.format(data,2) : '';}
            }*/
        ],
        fixedColumns: true,
        responsive:false,
        select:false,
        lengthMenu: [[10, 50, 100,-1], [10, 50, 100, "All"]]
    });
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
