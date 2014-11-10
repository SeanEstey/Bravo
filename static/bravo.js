//---------------------------------------------------------------
function useJQueryBtn() {
  $("input[type=submit], button")
    .button()
    .click(function( event ) {
      event.preventDefault();
    });
}

//---------------------------------------------------------------
function selectTemplateHandler() {
  var $select = $('#template-select');
  $select.change(function(){
    var $template = $select.find($('option:selected'));
    console.log($template.text());

    if($template.text() == 'Empties to Winn Reminder') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
    else if($template.text() == 'Special Message') {
      $('#special_msg_div').show();
      $('#order_div').show();
      $('#recorded_msg_div').show();
      $('#verify_phone_div').show();
    }
    else if($template.text() == 'Green Goods Delivery') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
    else if($template.text() == 'Empties to Winn Followup') {
      $('#special_msg_div').hide();
      $('#order_div').hide();
      $('#recorded_msg_div').hide();
      $('#verify_phone_div').hide();
    }
  });
}

//---------------------------------------------------------------
jQuery(function($){
  selectTemplateHandler();
  useJQueryBtn();
  $('#special_msg_div').hide();
  $('#order_div').hide();
  $('#recorded_msg_div').hide();
  $('#verify_phone_div').hide();

  $('#datepicker').datepicker();

  $submit_btn = $('#submit_btn');
  $submit_btn.click(function(){
    var paramObj = {};
    $.each($('form').serializeArray(), function(_, kv) {
      paramObj[kv.name] = kv.value;
    }); 

    var complete = true;
    var msg = "You forgot to enter the following fields: ";
    if(paramObj['time'] == '') {
      msg += "Call Time,";
      complete = false;
    }
    if(paramObj['date'] == '') {
      msg += " Call Date,";
      complete = false;
    }
    if(paramObj['csv'] == '') {
      msg += " Call Url";
      complete = false;
    }

    if(!complete) {
      //$('#dialog').find($('p')).text(JSON.stringify(paramObj)); 
      $('#dialog').find($('p')).text(msg);
     // $('#dialog').find($('label')).html(this.html().replace(/\n/g,'<br/>')); 
      //$('.ui-dialog-titlebar').hide();
      $('#dialog').dialog({ 
        buttons: [ { 
          text: "Ok", click: function() { $( this ).dialog( "close" ); } 
        } ], 
        width: 400,
        show: { effect: 'shake', duration:500},
        hide: { effect: 'fade'}
      });

    }
    else {
      $('form').submit(); 
    }
  });
});
