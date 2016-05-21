/* Library settings */

var Settings = {
  'bravo_php_url': "http://www.bravoweb.ca/php/views.php",
  'bravo_url': "http://www.bravoweb.ca",
  'calendar_color_id': {
    'light_purple' : 1,
    'aqua' : 2,
    'purple' : 3,
    'light_red' : 4,
    'yellow' : 5,
    'orange' : 6,
    'turqoise' : 7,
    'gray' : 8,
    'blue' : 9,
    'green' : 10,
    'red' : 11
  },
}

function Server() {}

Server.call = function(function_name, data, id) {
   var options = {
   'muteHttpExceptions': true,
   'method' : 'post',
   'payload' : {
     'keys': JSON.stringify({
       'association_name': id['association'],
       'etap_endpoint': id['endpoint'],
       'etap_user': id['user'],
       'etap_pass': id['pw']
     }),
     'func': function_name,
     'data' : JSON.stringify(data)}
  };
  
  var response = UrlFetchApp.fetch(Settings['bravo_php_url'], options);
  
  if(!response) {
    Logger.log('Unknown exception calling ' + function_name);
  //  log('Unknown exception calling ' + function_name, true);
    return false;
  }
  
  if(response.getResponseCode() != 200 && response.getResponseCode() != 408) {
    Logger.log(function_name + ' exception! : ' + JSON.stringify(response.getContentText()));
//    log(func_name + ' exception! : ' + response.getContentText(), true);
  }
   
  return response;
}