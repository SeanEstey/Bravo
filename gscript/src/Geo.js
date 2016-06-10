function Geo() {}

//---------------------------------------------------------------------    
Geo.findBlocksWithin = function(lat, lng, map_data, radius, end_date, cal_id, _events) {
  /* Return list of scheduled Blocks within given radius of lat/lng, up 
   * to end_date, sorted by date. Block Object defined in Config.
   * @radius: distance in kilometres
   * @map_data: JSON object with lat/lng coords
   * @events: optional list of calendar events
   *
   * Returns empty array if none found 
   */
    
  var events = _events || Schedule.getEventsBetween(cal_id, new Date(), end_date);
  
  var eligible_blocks = [];
  
  for(var i=0; i < map_data.features.length; i++) {
    var map_name = map_data.features[i].properties.name;
        
    var block = Schedule.findBlock(Parser.getBlockFromTitle(map_name), events);
    
    if(!block)
      continue;
    
    var center = Geo.centerPoint(map_data.features[i].geometry.coordinates[0]);
    
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
Geo.findMapTitle = function(lat, lng, map_data) {
  /* Returns the title of the map (from MAP_DATA) the provided coords belongs
   * to, false if no match found
   */
  
  for(var i=0; i < map_data.features.length; i++) {
    var map = Geo.getLatLng(map_data.features[i]);
    
    if(Geo.pointInPoly(map['lat'].length, map['lng'], map['lat'], lng, lat)) {
      Logger.log("Found map: %s", map_data.features[i].properties.name);
      
      return map_data.features[i].properties.name;
    }
  }
  
  return false;
}


//---------------------------------------------------------------------
Geo.geocodeBeta = function(address, city, postal) { 
  /* Returns most accurate Google Maps Geocoder result object.
   * If multiple results are returned, postal code is used to
   * discern correct match.
   * https://developers.google.com/maps/documentation/geocoding/start#geocoding-request-and-response-latitudelongitude-lookup
   * Returns result object: {
   *   "address_components" : [{
   *     "long_name" : "T2K 3Y1",
   *     "short_name" : "T2K 3Y1",
   *     "types" : [ "postal_code" ]
   *     },
   *     {...}
   *   ],
   *   "formatted_address" : "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
   *   "geometry" : {
   *     "location" : {   // This key only present is precise match found
   *       "lat" : 37.4224764,
   *       "lng" : -122.0842499
   *     },
   *     {...}
   *   },
   *   "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
   *   "partial_match": true  // This key only present if full match not found
   * }
   */
  
  try {
    var response = Maps.newGeocoder().geocode(address + ", " + city + ", AB");
  }
  catch(e) {
    Logger.log('geocode failed: ' + e.msg);
    return false;
  }
  
  if(response.results.length == 1 && 'partial_match' in response.results[0]) {
    Logger.log(
      'Warning: Only partial match found for "%s". Using "%s". Geo-coordinates may be incorrect.',
      address, response['results'][0]);
  }
  else if(response.results.length > 1) {
    Logger.log('Multiple results geocoded for "%s". Finding best match...', address);
    
    // No way to identify best match
    if(postal === undefined) {
      Logger.log('Warning: no postal code provided. Returning first result: "%s"',
                 response['results'][0]);
      return response.results[0];
    }
    
    // Let's use the Postal Code to find the best match
    for(var i=0; i<response.results.length; i++) {
      var result = response.results[i];
      
      var postal = '';
      
      for(var j=0; j<result.address_components.length; j++) {
        if(result.address_components[j]['types'].indexOf('postal_code') > -1)
          postal = result.address_components[j]['short_name'];
      }
      
      if(!postal)
        continue;
      
      if(postal.substring(0,3) == postal.substring(0,3)) {
        Logger.log(
          'First half of Postal Code "%s" matched in result[%s]: "%s". Using as best match.',
          postal, i, result['formatted_address']);
        return result;
      }
    }
    
    Logger.log(
      'Warning: unable to identify correct match. Using first result as best guess: %s',
      response['results'][0]['formatted_address']);
    
  }

  return response['results'][0];
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
    Logger.log('geocode failed: ' + e.msg);
    return false;
  }
  
  if(!r.results) {
    Logger.log('no result for geocode of ' + address_str);
    
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
