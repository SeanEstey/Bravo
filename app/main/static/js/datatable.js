/* datatable.js */

data = null;

//------------------------------------------------------------------------------
function initDatatable() {
    getData();
}

//------------------------------------------------------------------------------
function getData() {

    api_call(
      'datatable/get',
      data=null,
      function(response){
          console.log(format('%s datapoints received.', response['data'].length));
          data=response['data'];
          showData(data);
      });
}

//------------------------------------------------------------------------------
function showData(resp_data) {

    var data_hdr = ["date", "block", "skips", "orders", "zeros", "donors", "estmt", "receipt", "collectRate", "estmtMargin", "estmtTrend", "invoice", "tripSched", "mileage", "vehicle", "driver", "tripActual", "driverHrs", "cages"];
    var tbl_rows = [];
    var tbl_columns = [{title:'timestamp'}];
    for(var i=0; i<data_hdr.length; i++) {
        tbl_columns.push({title:Sugar.String.titleize(data_hdr[i])});
    }

    for(var i=0; i<resp_data.length; i++) {
        var fields = resp_data[i];
        var tbl_row = [fields['date']['$date']];
        for(var j=0; j<data_hdr.length; j++) {
            tbl_row.push(fields[data_hdr[j]] || ''); 
        }
        tbl_rows.push(tbl_row);
    }

    var table = $('#datatable').DataTable({
        data: tbl_rows,
        columns: tbl_columns,
        order: [[0,'desc']],
        columnDefs: [
            {
                "targets":0, // Timestamp
                "visible":false,
                "searchable":false
            },
            {
                "targets":data_hdr.indexOf('date')+1,
                "render": function(data, type, row) {return new Date(data['$date']).strftime('%b %d %Y');}
            },
            {
                "targets":[data_hdr.indexOf('receipt')+1, data_hdr.indexOf('estmt')+1],
                "render": function(data, type, row) { return data ? '$'+Sugar.Number.format(data,2) : '';}
            },
            {
                'targets':[data_hdr.indexOf('collectRate')+1, data_hdr.indexOf('estmtMargin')+1],
                'render':function(data,type,row){ return typeof(data)=='number' ? Sugar.Number.format(data*100,1)+'%' : '';}
            },
            {
                'targets':data_hdr.indexOf('estmtTrend')+1,
                'render':function(data,type,row){ return data ? '$'+Sugar.Number.format(data,2) : '';}
            },
            {
                'targets':data_hdr.indexOf('tripSched')+1,
                'render':function(data,type,row){ return data ? Sugar.Number.format(data,2) : '';}
            }
        ],
        responsive:true,
        select:false,
        lengthMenu: [[10, 50, 100,-1], [10, 50, 100, "All"]]
    });
}
