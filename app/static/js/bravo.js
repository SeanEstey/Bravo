function getServerStatus(variable) {
  var request =  $.ajax({
      type: 'GET',
      url: $URL_ROOT + 'get/' + variable
    });

  request.done(function(msg){
    console.log(msg);
  });
}

function displayServerStatus(route, label, $element) {
  var request =  $.ajax({
      type: 'GET',
      url: $URL_ROOT + route
    });

  request.done(function(msg){
    $element.html(msg.toTitleCase());
    $element.hide();
    $element.fadeIn('slow');
  });
}

