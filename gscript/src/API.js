//---------------------------------------------------------------------
function API(path, conf, data) {

  var payload = {};
  if(data) {
    for (var key in data) {
      if (data.hasOwnProperty(key)) {
        payload[key] = data[key];
      }
    }
  }
  
  var rv = UrlFetchApp.fetch(
    API_URL + path, {
    "headers": {"Authorization":"Basic "+ Utilities.base64Encode(conf["BRAVO_API_KEY"])},
    "muteHttpExceptions": true,
      "method" : "POST",
        "payload": payload
  });
  
  if(rv.getResponseCode() != 200) {
    Logger.log("%s exception: %s", path, JSON.stringify(rv.getContentText()));
    Browser.msgBox("Bravo Error: " + rv.getContentText());
    return rv.getContentText();
  }

  return JSON.parse(rv.getContentText())["data"];
}
