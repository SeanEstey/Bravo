//---------------------------------------------------------------------
function hashCode(str) {
  var hash = 0, i, chr, len;
  if (str.length === 0) return hash;
  for (i = 0, len = str.length; i < len; i++) {
    chr   = str.charCodeAt(i);
    hash  = ((hash << 5) - hash) + chr;
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
};

//---------------------------------------------------------------------
// For parsing Google Calendar events
function parseDate(string) {
  var parts = string.split('T');
  parts[0] = parts[0].replace(/-/g, '/');
  return new Date(parts.join(' '));
}

//---------------------------------------------------------------------
// Used to convert to eTapestry date format
function date_to_ddmmyyyy(date) {
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

//---------------------------------------------------------------------
function isNumber(obj) { return !isNaN(parseFloat(obj)) }


//---------------------------------------------------------------------
function shortenUrl() {

  var url = UrlShortener.Url.insert({
    longUrl: 'https://script.google.com/macros/s/AKfycbwau_pizWh_PaZ7U6uWiQisPpnmoSQJseEwuuNdTRl7ZefLfbU/exec'
  });
  Logger.log('Shortened URL is "%s".', url.id);
}


//---------------------------------------------------------------------
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

//---------------------------------------------------------------------
function setCellValue(sheet, row, col, value) {
  sheet.getRange(row, col).setValue(value);
}

//---------------------------------------------------------------------
function log_to_sheet(msg) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  if(!ss)
    return false;
  
  var log_sheet = ss.getSheetByName("Log");
  
  var date = new Date();
  var date_str = date.toDateString();
  var time_str = date.toLocaleTimeString();
  time_str = time_str.substring(0, time_str.length-3);
 
  var to_log = [[date_str + ' ' + time_str, msg]];
  
  log_sheet.getRange(
    log_sheet.getDataRange().getNumRows() + 1, 
    1, 
    1, 
    2)
    .setValues(to_log);
}

//---------------------------------------------------------------------
function write_logger() {  
  var log_data = Logger.getLog();
  
  if(log_data.length <= 0)
    return false;
    
  var log_sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName("Log");
  
  log_sheet.getRange(
    log_sheet.getDataRange().getNumRows()+1,1)
    .setValue(log_data);
  
  Logger.clear();
}

//---------------------------------------------------------------------
// to_sheet: true/false. If true, logs to Route Importer->Log sheet, if false,
// write to Logger.log
// mode: optional argument. If passed as 'Debug', msg will only log in Debug mode.
function log(msg, to_sheet, mode) {
  if (mode == undefined)
    Logger.log(msg);
  else if (mode == 'Debug' && Config['debug_mode'])
    Logger.log(msg);
  
  if(to_sheet != undefined) {
    Logger.log(msg)
    log_to_sheet(msg);
  }
}

//---------------------------------------------------------------------
function toTitleCase(str) {
  return str.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
}

function addCellValue(sheet, row, col, value) {
  var range = sheet.getRange(row, col);
  range.setValue(range.getValue() + '\n' + value); 
}

//---------------------------------------------------------------------
function appendCellNote(range, note) {

  if(range.getNote())
    range.setNote(range.getNote() + '\n' + note);
  else
    range.setNote(note);
}

