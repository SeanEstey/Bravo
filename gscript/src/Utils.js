function isNumber(obj) { return !isNaN(parseFloat(obj)) }

function toTitleCase(str) {
  return str.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
}

function appendRowsToSheet(sheet, data, start_column) {
  if(!data.length)
    return false;
  
  var range = sheet.getRange(
    sheet.getLastRow() + 1,
    start_column,
    data.length,
    data[0].length);
  
  range.setValues(data);
};

function appendCellNote(range, note) {
  if(range.getNote())
    range.setNote(range.getNote() + '\n' + note);
  else
    range.setNote(note);
}

function parseDate(string) {
  /* For parsing Google Calendar events
  */
  var parts = string.split('T');
  parts[0] = parts[0].replace(/-/g, '/');
  return new Date(parts.join(' '));
}

function date_to_ddmmyyyy(date) {
  /* Used to convert to eTapestry date format
  */
  
  if(!date)
    return;
  
  var day = date.getDate();
  if(day < 10)
    day = '0' + String(day);
  
  var month = date.getMonth() + 1;
  if(month < 10)
    month = '0' + String(month);
  
  return day + '/' + month + '/' + String(date.getYear());
}

function log(msg, to_sheet, mode) {
  /* @to_sheet: true/false. If true, logs to Route Importer->Log sheet, if false,
   * write to Logger.log
   * mode: optional argument. If passed as 'Debug', msg will only log in Debug mode.
   */
  if (mode == undefined)
    Logger.log(msg);
  else if (mode == 'Debug' && Config['debug_mode'])
    Logger.log(msg);
  
  if(to_sheet != undefined) {
    Logger.log(msg)
  }
}
