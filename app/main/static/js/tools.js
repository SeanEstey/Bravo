/* tools.js */

map_data = {};

function parse_neighb(title) { return title.slice(title.indexOf('[')+1, title.indexOf(']')); }
function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//------------------------------------------------------------------------------
function tools_init() {
    
    $('#update_maps').click(update_map_data)
    $('#map_select').change(load_map);
    $('#analyze').click(analyze_blocks);

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
          console.log(response);
      });
}

//------------------------------------------------------------------------------
function get_maps() {
    /* From Bravo */

    api_call(
      'maps/get',
      data=null,
      function(response){
          console.log(response);
          map_data = response['data'];
          var maps = map_data['features'];

          $('#map_count').text(maps.length);
          $('#last_updated').text(new Date(map_data['update_dt']['$date']).strftime("%B %d %H:%M:%S %p"));

          for(var i=0; i<maps.length; i++) {
              $('#map_select').append(
                '<option value='+i+'>'+maps[i]['properties']['name']+'</option>');
          }
      }
    );
}

//------------------------------------------------------------------------------
function load_map() {

    console.log('selected option ' + this.value);
    
    var map_idx = this.value;
    var maps = map_data['features'];
    var map = map_data['features'][this.value];
    var title = map['properties']['name'];
    var desc = map['properties']['description'];
    

    $('#block').text(title.slice(0, title.indexOf(' ')));
    $('#neighborhoods').text(parse_neighb(title));
    $('#description').html(desc);
    $('#n_coords').text(map['geometry']['coordinates'][0].length);

    var l_areas = parse_neighb(map['properties']['name']).split(", ");
    var blocks = [];

    console.log('Finding maps matching areas: ' + l_areas);
    
    for(var i=0; i<maps.length; i++) {
        if(i == map_idx)
            continue;

        var r_areas = parse_neighb(maps[i]['properties']['name']).split(", ");

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
function analyze_blocks() {

    var map_title = $('#map_select option:selected').text();
    var blocks = $('#search_blocks').text().split(",");

    console.log('Analyzing accounts within map "' + map_title + '". Searching Blocks: ' + blocks);

    api_call(
      'accounts/find_within_map',
      data={
        'map_title': map_title,
        'blocks': JSON.stringify(blocks)},
      function(response){
          console.log(response);
          alertMsg('Running analysis for accounts within ' + map_title + '.', 'info', 60000);
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

    socket.on('analyze_results', function(data) {
        if(data['status'] == 'match') {
            console.log('Found match: Acct ID ' + data['acct_id']);

            $('#n_matches').text(data['n_matches']);
            $('#acct_ids').text($('#acct_ids').text() + ", " + String(data['acct_id']));
        }
        else if(data['status'] == 'completed') {
            console.log('Total matches: ' + data['n_matches']);
            alertMsg('Analysis complete. ' + data['n_matches'] + ' account matches found', 'success');
        }
    });
}
