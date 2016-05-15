function Geo() {}

//---------------------------------------------------------------------    
Geo.findBlocksWithin = function(lat, lng, radius, end_date) {
  /* Return list of scheduled Blocks within given radius of lat/lng, up 
   * to end_date, sorted by date. Block Object defined in Config.
   * Returns empty array if none found 
   */
  
  var today = new Date();
  var events = Schedule.getCalEventsBetween(Config['res_calendar_id'], today, end_date);
  
  var eligible_blocks = [];
  
  for(var i=0; i<MAP_DATA.features.length; i++) {
    var map_name = MAP_DATA.features[i].properties.name;
     
    var block = Schedule.getNextBlock(events, Parser.getBlockFromTitle(map_name));
    
    if(!block)
      continue;
    
    var center = Geo.centerPoint(MAP_DATA.features[i].geometry.coordinates[0]);
    
    // Take the first lat/lon vertex in the rectangle and calculate distance
    var dist = Geo.distance(lat, lng, center[1], center[0]);
    
    if(dist > radius)
      continue;
    
    if(block['date'] <= end_date) {
      block['distance'] = dist.toPrecision(2).toString() + 'km';
      eligible_blocks.push(block);
    }
  }
  
  if(eligible_blocks.length > 0) {
    eligible_blocks.sort(function(a, b) {
      if(a.date < b.date)
        return -1;
      else if(a.date > b.date)
        return 1;
      else
        return 0;
    });
    
    Logger.log('Found ' + eligible_blocks.length + ' results within radius');
  }
  
  return eligible_blocks;
}

//---------------------------------------------------------------------    
Geo.centerPoint = function(arr){
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

//---------------------------------------------------------------------
Geo.distance = function(lat1, lon1, lat2, lon2) {
  /* Calculates KM distance between 2 lat/lon coordinates */
  
  var p = 0.017453292519943295;    // Math.PI / 180
  var c = Math.cos;
  var a = 0.5 - c((lat2 - lat1) * p)/2 + 
          c(lat1 * p) * c(lat2 * p) * 
          (1 - c((lon2 - lon1) * p))/2;

  return 12742 * Math.asin(Math.sqrt(a)); // 2 * R; R = 6371 km
}


//---------------------------------------------------------------------
Geo.pointInPoly = function(nvert, vertx, verty, testx, testy) {
  /* Returns true if a vertex lies within the area of a given polygon,
   * returns 0.0 otherwise (falsy)
   */
  
  var i, j, c = 0;
  for (i = 0, j = nvert-1; i < nvert; j = i++) {
   if( ((verty[i]>testy) != (verty[j]>testy)) &&
   (testx < (vertx[j]-vertx[i]) * (testy-verty[i]) / (verty[j]-verty[i]) + vertx[i]) )
    c = !c;
  }
  
  return c;
}
 

//---------------------------------------------------------------------
Geo.getLatLng = function(kml_map) {
  /* Returns object containing separate lists of lat/lng coords
   * kml_map is an object from MAP_DATA['features'][idx]
   */
  
  var lat = [];
  var lng = [];
  
  for(var i=0; i < kml_map.geometry.coordinates[0].length; i++) {
    lng.push(kml_map.geometry.coordinates[0][i][0]);
    lat.push(kml_map.geometry.coordinates[0][i][1]);
  }
  
  return {'lat':lat, 'lng':lng};
}


//---------------------------------------------------------------------
Geo.findMapTitle = function(lat, lng) {
  /* Returns the title of the map (from MAP_DATA) the provided coords belongs
   * to, false if no match found
   */
  
  for(var i=0; i < MAP_DATA.features.length; i++) {
    var map = Geo.getLatLng(MAP_DATA.features[i]);
    
    if(Geo.pointInPoly(map['lat'].length, map['lng'], map['lat'], lng, lat)) {
      Logger.log("Found map: %s", MAP_DATA.features[i].properties.name);
      
      return MAP_DATA.features[i].properties.name;
    }
  }

  Logger.log("find_map: Could not find map");
  
  return false;
}


//---------------------------------------------------------------------
Geo.geocode = function(address_str) {  
  /* Wrapper for Google Maps geocoder, returns object with properties:
   * "Neighborhood": str, "Coords": lat/lng array, "Postal_Code": str,
   * "Partial_Match": bool
   */
  
  try {
    var r = Maps.newGeocoder().geocode(address_str);
  }
  catch(e) {
    log('geocode failed: ' + e.msg);
    return false;
  }
  
  if(!r.results) {
    log('no result for geocode of ' + address_str);
    
    return false;
  }
  
  if(r.results > 0) {
    Logger.log('Multiple results found: ' + r.results);
  }
  
  var result = r.results[0];
  
  var geo_info = { 
    "Neighborhood": false,
    "Coords": [],
    "Postal_Code": false,
    "Partial_Match": false
  };
  
  if(result.partial_match)
    geo_info.Partial_Match = true;
    
  for(var i=0; i<result.address_components.length; i++) {
    if(result.address_components[i].types.indexOf('neighborhood') == -1)
      continue;
    
    geo_info.Neighborhood = result.address_components[i].long_name;
      
    Logger.log("Found neighborhood match for '%s': %s",
                 address_str,  geo_info.Neighborhood);
  }
  
  for(var i=0; i<result.address_components.length; i++) { 
    if(result.address_components[i].types.indexOf("postal_code") == -1) 
      continue;
 
      var postal = result.address_components[i].long_name;
      
      if(postal.length == 7)
        geo_info.Postal_Code = postal;
  }

 if(result.geometry.location) 
   geo_info.Coords = result.geometry.location;
  
  return geo_info;
}
