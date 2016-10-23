
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

