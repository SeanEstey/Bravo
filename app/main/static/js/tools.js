/* tools.js */

map_data = {};
matches = [];

function parse_areas(title) { return title.slice(title.indexOf('[')+1, title.indexOf(']')); }
function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//------------------------------------------------------------------------------
function tools_init() {
    
    $('#update_maps').click(update_map_data)
    $('#map_select').change(show_map_properties);
    $('#analyze').click(run_analyzer);

    $('.tab-content').prepend($('.alert-banner'));
    alertMsg("Loading maps...", "info");

    get_maps();
    init_socketio();
}

//------------------------------------------------------------------------------
function update_map_data() {
    /* Refresh map data from Google My Maps. 
     * Calls async server process. Wait for socketio message on_complete. */

    api_call(
      'maps/update',
      data=null,
      function(response){
          alertMsg(JSON.stringify(response), 'info');
      });
}

//------------------------------------------------------------------------------
function get_maps() {
    /* From Bravo */

    $('#map_count').text("...");
    $('#last_updated').text("...");

    api_call(
      'maps/get',
      data=null,
      function(response){
          console.log(response);

          var MAX_CHARS = 40;
          map_data = response['data'];
          var maps = map_data['features'];

          $('#map_count').text(maps.length);
          $('#last_updated').text(new Date(map_data['update_dt']['$date']).strftime("%B %d %H:%M:%S %p"));
          $('#map_select').empty();

          for(var i=0; i<maps.length; i++) {
              var title = maps[i]['properties']['name'];

              if(title.length > MAX_CHARS)
                  title = title.slice(0, MAX_CHARS) + "...";

              $('#map_select').append(
                '<option value='+i+'>' + title);
          }

          var options = $("#map_select option");
          options.sort(function(a,b) {
              if (a.text > b.text) return 1;
              if (a.text < b.text) return -1;
              return 0
          })

          $("#map_select").append('<option value="" disabled selected>Select a Map</option>').append(options);

          fadeAlert();
      }
    );
}

//------------------------------------------------------------------------------
function show_map_properties() {

    var map_idx = this.value;
    var maps = map_data['features'];
    var map = map_data['features'][this.value];
    var title = map['properties']['name'];
    var desc = map['properties']['description'];
    
    $('#block').text(title.slice(0, title.indexOf(' ')));
    $('#neighborhoods').text(parse_areas(title));
    $('#description').html(desc);
    $('#n_coords').text(map['geometry']['coordinates'][0].length);

    var l_areas = parse_areas(map['properties']['name']).split(", ");
    var blocks = [];

    for(var i=0; i<maps.length; i++) {
        var r_areas = parse_areas(maps[i]['properties']['name']).split(", ");

        for(var j=0; j<l_areas.length; j++) {
            if(r_areas.indexOf(l_areas[j]) > -1) {
                blocks.push(parse_block(maps[i]['properties']['name']));
                break;
            }
        }
    }
    $('#search_blocks').text(blocks);
}

//------------------------------------------------------------------------------
function run_analyzer() {

    var map_title = $('#map_select option:selected').text();
    var blocks = $('#search_blocks').text().split(",");

    matches = [];
    $('#acct_ids').text("None");
    $('#n_matches').text("None");

    api_call(
      'accounts/find_within_map',
      data={
        'map_title': map_title,
        'blocks': JSON.stringify(blocks)},
      function(response){
          console.log(response);
          
          $('#analyze').prop('disabled', true);
          $('#map_select').prop('disabled', true);
          $('#update_maps').prop('disabled', true);
          alertMsg('Running analysis for accounts within ' + map_title + '...', 'info');
          $('#status').text("Running...");
      });
}

//------------------------------------------------------------------------------
function init_socketio() {

    socket = io.connect('https://' + document.domain + ':' + location.port);

    socket.on('connect', function(){
        console.log('socket.io connected');
        socket.on('joined', function(response) {
            console.log(response);
        });
    });

    socket.on('analyze_results', function(rv) {
        if(rv['status'] == 'match') {
            if(matches.indexOf(rv['acct_id']) > -1)
                return;

            matches.push(rv['acct_id']);
            $('#n_matches').text(rv['n_matches']);
            $('#acct_ids').text(matches.join(", "));
        }
        else if(rv['status'] == 'completed') {
            alertMsg('Analysis complete. ' + rv['n_matches'] + ' account matches found. Results written to <a href="https://docs.google.com/spreadsheets/d/1JjibGqBivKpQt4HSW0RFfuTPYAI9LxJu-QOd6dWySDE/edit#gid=1060952486">Bravo Sheets</a>', 'success', -1);
            
            $('#status').text("Finished");
            $('#analyze').prop('disabled', false);
            $('#map_select').prop('disabled', false);
            $('#update_maps').prop('disabled', false);
        }
    });
}
