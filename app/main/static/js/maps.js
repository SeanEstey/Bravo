/* maps.js */

gmaps = null;
map_data = {};
polygons = null;
markers = null;
current_polygon = null;
current_marker = null;

DEF_ZOOM = 11;
DEF_MAP_ZOOM = 14;
MAX_ZOOM = 21;
HOME_ICON = "https://bravoweb.ca/static/main/images/house_map_icon.png";
MAP_FILL ='#99ccff';
MAP_STROKE = '#6666ff';

CITY_COORDS = $('#coord_data').data()['city'];
HOME_COORDS = $('#coord_data').data()['home'];

function parse_block(title) { return title.slice(0, title.indexOf(' ')); }

//------------------------------------------------------------------------------
function initGoogleMap() {

    gmaps = new google.maps.Map(
        $('#map')[0],
        {mapTypeId:'roadmap', center:CITY_COORDS, zoom:DEF_ZOOM}
    );


}

//------------------------------------------------------------------------------
function loadMapData() {

    api_call(
      'maps/get',
      data=null,
      function(response){
          if(response['status'] == 'success') {
              console.log('Map data loaded');

              map_data = response['data'];
              var block = $('#coord_data').data()['block'];

              for(var i=0; i<map_data['features'].length; i++) {
                  var feature = map_data['features'][i];
                  if(parse_block(feature['properties']['name']) == block) {
                      console.log('Drawing ' + block);
                      drawMapPolygon(feature['geometry']['coordinates'][0]);
                      break;
                  }
              }
          }
      }
    );
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

    if(current_polygon)
        current_polygon.setMap(null);

    current_polygon = new google.maps.Polygon({
        paths: paths,
        strokeColor: MAP_STROKE,
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: MAP_FILL,
        fillOpacity: 0.35
    });

    current_polygon.setMap(gmaps);

    var _coords = coords.slice();

    if(current_marker){
        var marker_coords = JSON.parse(JSON.stringify(current_marker.getPosition()));
        paths.push(marker_coords)
        paths.push(HOME_COORDS);
        _coords.push([marker_coords['lng'],marker_coords['lat'],0]);
        _coords.push([HOME_COORDS['lng'], HOME_COORDS['lat'], 0]);
    }

    var center = centerPoint(_coords);
    gmaps.setCenter({'lat':center[1], 'lng':center[0]});
    setOptimalZoom(paths);
}

//---------------------------------------------------------------------    
function addMarker(title, coords, icon) {

    var options = {
        position: coords,
        clickable: true,
        map: gmaps,
        title: title
    };

    if(icon)
        options['icon'] = icon;

    return new google.maps.Marker(options);
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
