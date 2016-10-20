// GLOBALS
this.colors = {
  'SUCCESS_STATUS': '#5CB85C',
  'FAILED_STATUS': '#D9534F',
  'DEFAULT_STATUS': 'black',
  'IN_PROGRESS_STATUS': '#337AB7'
};
	
this.unicode = {
  'UP_ARROW': '&#8593;',
  'DOWN_ARROW': '&#8595;',
  'SPACE': '&#32;'
};

//------------------------------------------------------------------------------
function HTMLEncode(str) {
  // Returns decimal code for special HTML characters

  var i = str.length,
    aRet = [];

  while (i--) {
    var iC = str[i].charCodeAt();
    if (iC < 65 || iC > 127 || (iC > 90 && iC < 97)) {
      aRet[i] = '&#' + iC + ';';
    } else {
      aRet[i] = str[i];
    }
  }
  return aRet.join('');
}

//------------------------------------------------------------------------------
String.prototype.toTitleCase = function(n) {
  // Replace underscores with spaces, capitalizes words

   var s = this;
   if (1 !== n) 
     s = s.toLowerCase();
   s = s.replace(/_/g, ' ');
   return s.replace(/\b[a-z]/g,function(f){return f.toUpperCase()});
}

//------------------------------------------------------------------------------
function addBravoTooltip() {
  $(document).tooltip({
    position: {
      my: 'center bottom-20',
      at: 'center top',
      using: function(position, feedback) {
        $(this).css(position);
        $('<div>')
          .addClass('arrow')
          .addClass(feedback.vertical)
          .addClass(feedback.horizontal)
          .appendTo(this);
      }
    }
  });
}

//------------------------------------------------------------------------------
function showDialog($element, msg, _title, _buttons) {
	/* Error/confirmation dialog UI for all views */

  if(typeof(_buttons) === 'undefined') {
      _buttons = [{ 
        text: "Sorry, I'll fix it", 
        click: function() { $( this ).dialog( "close" ); }
      }];
  }

  if(typeof(_title) === 'undefined') {
    _title = 'What have you done??'
  }

  var dialog_style = { 
    modal: true,
    title: _title,
    dialogClass: 'ui-dialog-osx',
    width: 500,
    height: 'auto',
    buttons: _buttons,
    show: { effect: 'fade', duration:150},
    hide: { effect: 'fade', duration:150}
  };
  
  // MUST have a <p> element for the msg
  $element.find($('p')).html(msg);
  $element.dialog(dialog_style);
}

//------------------------------------------------------------------------------
function objToHtml(obj, indents, ignores) {
  /*Converts a JS Object to indented, color-coded HTML (no braces/brackets)
  Properties are sorted alphabetically
  */

  var indent = '';
  var str = '';
  var toClass = {}.toString;
  for(var i=0; i<indents; i++)
    indent += '&nbsp;&nbsp';

  var sorted_keys = Object.keys(obj).sort();
  var key;

  for(var index in sorted_keys) {
    key = sorted_keys[index];
    if(ignores.indexOf(key) > -1)
      continue;
    // MongoDB Timestamp
    if(key.indexOf('$date') > -1) {
      str += indent + 'Date: ';
      var date_str = new Date(obj[key]);
      str += '<label style="color:green;">' + date_str + '</label><br>'; 
    }
    // Primitive
    else if(typeof obj[key] != 'object') {
      str += indent + key.toTitleCase() + ': ';
      str += '<label style="color:green;">' + String(obj[key]) + '</label><br>';
    }
    // Date
    else if(toClass.call(obj[key]) == '[object Date]')
      str += indent + key.toTitleCase() + ': ' + obj[key].toString() + '<br>';
    // Array
    else if(toClass.call(obj[key]) == '[object Array]') {
      str += indent + key.toTitleCase() + ': <br>';
      var element_str;
      for(var i=0; i<obj[key].length; i++) {
        element_str = objToHtml(obj[key][i], indents+1, ignores);
        str += indent + element_str + '<br>';
      }
    }
    // Generic Object
    else if(toClass.call(obj[key]) == '[object Object]') {
      var obj_str = objToHtml(obj[key], indents+1, ignores);
      str += indent + key.toTitleCase() + '<br>' + obj_str;
    }
  }
  return str;
}

//------------------------------------------------------------------------------
function bannerMsg(msg, type, duration=5000) {
		var $banner = $('.status-banner');

		if(!$banner)
				return false;
		
		if(type == 'info')
			$banner.css('background-color', 'CDE6CD'); 
		else if(type == 'error')
			$banner.css('background-color', 'FFCCCC'); 

		$banner.css('visibility', 'visible');
		$banner.css('opacity', 0);

		$banner.text(msg);
		$banner.clearQueue();

		$banner.fadeTo('slow', 1);

		if(type == 'info')
				$banner.delay(duration);
		else if(type == 'error')
				$banner.delay(10000);
	
		$banner.fadeTo('slow', 0);
}
