/* utils.js 
   String-related utility functions.
*/

//---------------------------------------------------------------------
function format(str) {
  /* str: "Hello %s, my name is %s" 
     args: one for each %s 
  */ 

  var args = [].slice.call(arguments, 1), i = 0;
  return str.replace(/%s/g, function() {return args[i++];});
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
