/**
 * Module dependencies.
 */

var api_key = 'key-d52538f30cff03fdaab2659c76e4474a';
var domain = 'wsaf.ca';

var express = require('express');
var bodyParser = require('body-parser');
var app = express();
var mailgun = require('mailgun-js')({apiKey: api_key, domain: domain});

app.use(bodyParser.urlencoded({extended:false}));

app.get('/', function(request, response) {
  console.log('node js GET request');
  response.end('node.js GET received');
});

app.post('/', function(request, response) {
  console.log('node.js POST request');
  response.end('node.js POST received');
  
  var data = {
    from: 'Sean <emptiestowinn@wsaf.ca>',
    to: 'estese@gmail.com',
    subject: 'Bravo Inquiry',
    text: 
      'First: ' + request.body.first_name + '<br>' +
      'Last: ' + request.body.last_name + '<br>' +
      'Phone: ' + request.body.phone + '<br>' +
      'Details: ' + request.body.details
  };
   
  mailgun.messages().send(data, function (error, body) {
    console.log(body);
  });
});





app.listen(3000, function() {
  console.log('Node.js server started on port 3000');
});





