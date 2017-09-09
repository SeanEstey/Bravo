

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
          showData();
      });
}

//------------------------------------------------------------------------------
function showData() {

    var $dt = $('#datatable');
    $dt.find('thead').empty();
    $dt.find('tbody').empty();

    var headers = Object.keys(data[0]);

    headers.splice(headers.indexOf('routeNotes'),1);
    headers.splice(headers.indexOf('_id'),1);
    headers.splice(headers.indexOf('inspection'),1);
    headers.splice(headers.indexOf('date'),1);
    headers = ['date'].concat(headers);

    $dt.find('thead').append('<tr></tr>');

    for(var i=0; i<headers.length; i++) {
        var hdr = headers[i];
        $dt.find('thead tr').append('<th>'+hdr+'</th>');
    }

    for(var i=0; i<data.length; i++) {
        var row_data = data[i];
        var $row = $('<tr></tr>');

        for(var k=0; k<headers.length; k++) {
            var hdr = headers[k];

            if(row_data.hasOwnProperty(hdr)) {
                var $td = $('<td></td>');
                var val = row_data[hdr];

                if(hdr == 'date') {
                    val = new Date(val['$date']);
                    val = val.strftime('%b %d %Y');
                    $td.css('min-width', '100px');
                }
                else if(typeof(val) == 'number') {
                    val = Sugar.Number.abbr(val,1);
                }

                $td.append(val);
                $row.append($td);
            }
            else {
                $row.append('<td>N/A</td>');
            }
        }

        $dt.find('tbody').append($row);
    }

    $('#datatable').DataTable({
        responsive:true,
        select:true,
        "lengthMenu": [[100, 250,-1], [100, 250, "All"]]
    });

    $('#datatable').show();
}
