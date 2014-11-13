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
  $('#datepicker').datepicker();
  $("input[type=file]").nicefileinput();

  $submit_btn = $('#submit_btn');
  $submit_btn.click(function(){
    var paramObj = {};
    $.each($('form').serializeArray(), function(_, kv) {
      paramObj[kv.name] = kv.value;
    }); 

    // Validate form data
    var missing = [];
    var filename = $('#call-list-div').val();
    var wrong_date = false;
    var wrong_filetype = false;
    var scheduled_date = null;
    
    if(!filename)
      missing.push('CSV File');
    else if(filename.indexOf('.csv') <= 0)
      wrong_filetype = true;
    if(!paramObj['time'])
      missing.push('Schedule Time');
    if(!paramObj['date'])
      missing.push('Schedule Date');
    else {
      var now = new Date();
      var date_str = paramObj['date'];
      if(paramObj['time'])
        date_str += ', ' + paramObj['time'];
      // Datejs for parsing strings like '12pm'
      scheduled_date = Date.parse(date_str);
      console.log(scheduled_date.toString());
      if(scheduled_date.getTime() < now.getTime())
        wrong_date = true;
    }

    var msg = ''; 
    if(missing.length > 0) {
      msg = 'You forgot to enter: ';
      msg += '<b>' + missing.join(', ') + '</b><br><br>';
    }
    if(wrong_filetype)
      msg += 'The file you selected is not a .CSV';

    var dialog_style = { 
      modal: true,
      title: 'What have you done?!',
      dialogClass: 'ui-dialog-osx',
      width: 500,
      height: 'auto',
      show: { effect: 'fade', duration:150},
      hide: { effect: 'fade', duration:150}
    };

    if(missing.length > 0 || wrong_filetype) {
      $('#dialog').find($('p')).html(msg);
      dialog_style['buttons'] = [
        { text: "Sorry, I'll fix it", 
         click: function() { $( this ).dialog( "close" ); }}
      ];
      $('#dialog').dialog(dialog_style);
    }
    else if(wrong_date) {
      msg = 'The scheduled date is before the present:<br><br>' + 
      '<b>' + scheduled_date.toString('dddd, MMMM d, yyyy @ hh:mm tt') + '</b><br><br>' +
      'Do you want to start this job now?';

      $('#dialog').find($('p')).html(msg);
      dialog_style['buttons'] = [
        { text: "No, let me fix it", 
          click: function() { $( this ).dialog( "close" ); }}, 
        { text: 'Yes, start job now', 
          click: function() { $(this).dialog('close'); $('form').submit();}}
      ];
      $('#dialog').dialog(dialog_style);
    }
    else {
      $('form').submit(); 
    }
  });
});