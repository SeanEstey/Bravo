/* tools.js */

gmaps = null;
map_data = {};
shapes = [];
markers = [];
current_map = null;
matches = [];
overlap_blocks = [];

DEF_ZOOM = 11;
DEF_MAP_ZOOM = 14;
MAX_ZOOM = 21;
CALGARY = {lat:51.055336, lng:-114.077959};
MAP_FILL ='#99ccff';
MAP_STROKE = '#6666ff';

function parse_areas(title) { return title.slice(title.indexOf('[')+1, title.indexOf(']')); }
function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//------------------------------------------------------------------------------
function init() {
    
    $('#update_maps').click(syncMapData)
    $('#map_select').change(selectMap);
    $('#analyze').click(runAnalyzer);

    $('.tab-content').prepend($('.alert-banner'));
    alertMsg("Loading maps...", "info");

    loadMapData();
    initSocketIO();
}

//------------------------------------------------------------------------------
function initGoogleMap() {

    gmaps = new google.maps.Map(
        $('#map')[0],
        {mapTypeId:'roadmap', center:CALGARY, zoom:DEF_ZOOM}
    );
}

//------------------------------------------------------------------------------
function initSocketIO() {

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

            addMarker('Account #' + rv['acct_id'], rv['coords']);
            matches.push(rv['acct_id']);

            $('#n_matches').text(rv['n_matches']);
        }
        else if(rv['status'] == 'completed') {
            $('#status').text("Finished");
            $('#analyze').prop('disabled', false);
            $('#map_select').prop('disabled', false);
            $('#update_maps').prop('disabled', false);

            alertMsg(
              'Analysis complete. '+rv['n_matches']+' account matches found. '+
              'Results written to Bravo Sheets.', 'success', -1);
        }
    });
}

//------------------------------------------------------------------------------
function syncMapData() {
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
function loadMapData() {
    /* From Bravo */

    $('#map_count').text("...");
    $('#last_updated').text("...");

    api_call(
      'maps/get',
      data=null,
      function(response){
          console.log('maps/get status: '+response['status']);

          map_data = response['data'];
          var maps = map_data['features'];

          $('#map_count').text(maps.length);
          $('#last_updated').text(
              new Date(map_data['update_dt']['$date'])
              .strftime("%B %d %H:%M:%S %p"));
          $('#map_select').empty();

          for(var i=0; i<maps.length; i++) {
              var title = maps[i]['properties']['name'];

              if(title.length > 40)
                  title = title.slice(0, 40) + "...";

              $('#map_select').append(
                '<option value='+i+'>' + title);
          }

          var options = $("#map_select option");
          options.sort(function(a,b) {
              if (a.text > b.text) return 1;
              if (a.text < b.text) return -1;
              return 0
          })

          $("#map_select").append(
            '<option value="" disabled selected>Select a Map</option>')
            .append(options);
          fadeAlert();
      }
    );
}

//------------------------------------------------------------------------------
function selectMap() {

    current_map = map_data['features'][this.value];
    var this_title = current_map['properties']['name'];
    var this_areas = parse_areas(current_map['properties']['name']).split(", ");
    overlap_blocks = [];

    $('#block').text(this_title.slice(0, this_title.indexOf(' ')));
    $('#neighborhoods').text(parse_areas(this_title));
    $('#description').html(current_map['properties']['description']);
    $('#n_coords').text(current_map['geometry']['coordinates'][0].length);

    for(var i=0; i<map_data['features'].length; i++) {

        var a_map = map_data['features'][i];
        var a_title = a_map['properties']['name'];
        var a_areas = parse_areas(a_title).split(', ');

        for(var j=0; j<this_areas.length; j++) {
            if(a_areas.indexOf(this_areas[j]) > -1) {
                overlap_blocks.push(parse_block(a_title));
                break;
            }
        }
    }

    $('#search_in').text(overlap_blocks);

    clearMap();
    drawMapPolygon(current_map['geometry']['coordinates'][0]);
}

//---------------------------------------------------------------------    
function centerPoint(arr){
  /* Returns [x,y] coordinates of center of polygon passed in */
  
    var minX, maxX, minY, maxY;
    for(var i=0; i< arr.length; i++){
        minX = (arr[i][0] < minX || minX == null) ? arr[i][0] : minX;
        maxX = (arr[i][0] > maxX || maxX == null) ? arr[i][0] : maxX;
        minY = (arr[i][1] < minY || minY == null) ? arr[i][1] : minY;
        maxY = (arr[i][1] > maxY || maxY == null) ? arr[i][1] : maxY;
    }
    return [(minX + maxX) /2, (minY + maxY) /2];
}

//------------------------------------------------------------------------------
function drawMapPolygon(coords) {

    var paths = [];
    for(var i=0; i<coords.length; i++) {
        paths.push({"lat":coords[i][1], "lng":coords[i][0]});
    }

    var shape = new google.maps.Polygon({
        paths: paths,
        strokeColor: MAP_STROKE,
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: MAP_FILL,
        fillOpacity: 0.35
    });
    shape.setMap(gmaps);
    shapes.push(shape);

    var center = centerPoint(coords);
    gmaps.setCenter({'lat':center[1], 'lng':center[0]});
    setOptimalZoom(paths);
}

//------------------------------------------------------------------------------
function setOptimalZoom(paths) {

    var zoom = DEF_MAP_ZOOM;
    gmaps.setZoom(zoom);
    var bounds = gmaps.getBounds();

    if(inBounds(bounds, paths)) {
        while(inBounds(gmaps.getBounds(), paths) && zoom <= MAX_ZOOM) {
            gmaps.setZoom(++zoom);
        }

        // Zoom back out one level
        gmaps.setZoom(--zoom);
    }
    else {
        while(!inBounds(gmaps.getBounds(), paths)) {
            gmaps.setZoom(--zoom);
        }
    }

    console.log('Optimal zoom set to ' + zoom);
}

//------------------------------------------------------------------------------
function inBounds(bounds, paths) {

    for(var i=0; i<paths.length; i++) {
        if(!bounds.contains(paths[i]))
            return false;
    }

    return true;
}

//---------------------------------------------------------------------    
function addMarker(title, coords) {

    markers.push(new google.maps.Marker({
        position: coords,
        map: gmaps,
        title: title
    }));
}

//------------------------------------------------------------------------------
function clearMap() {
    /* Remove all polygons and markers */

    for(var i=0; i<shapes.length; i++) {
        shapes[i].setMap(null);
    }

    for(var i=0; i<markers.length; i++) {
        markers[i].setMap(null);
    }
}

//------------------------------------------------------------------------------
function runAnalyzer() {

    matches = [];
    $('#n_matches').text("None");

    api_call(
      'accounts/find_within_map',
      data={
        'map_title': current_map['properties']['name'],
        'blocks': JSON.stringify(overlap_blocks)},
      function(response){
          $('#analyze').prop('disabled', true);
          $('#map_select').prop('disabled', true);
          $('#update_maps').prop('disabled', true);
          $('#status').text("Running...");

        var title = $('#map_select option:selected').text();
          alertMsg('Running analysis for accounts within ' + title + '...', 'info');
      });
}
