//------------------------------------------------------------------------------
function StatsManager(conf) {
  this.conf = conf;
}

//------------------------------------------------------------------------------
StatsManager.prototype.writeStats = function(route) {
  
  if(this.conf['AGCY'] == 'vec') {
    updateVecStats(
      route,
      this.conf['STATS_SS_ID']);
  }
  else if(this.conf['AGCY'] == 'wsf') {
    updateWsfStats(
      route,
      this.conf['STATS_SS_ID'],
      this.conf['STATS_ARCHV_SS_ID']);
  }
}

//------------------------------------------------------------------------------
StatsManager.prototype.writeInventory = function(route) {
  
  var START_ROW = 7;
  if(!this.conf['INVEN_SS_ID'])
    return;
  var ss = SpreadsheetApp.openById(this.conf['INVEN_SS_ID']);
  if(!ss)
    return;
  var inven_wks = ss.getSheetByName(MONTHS[route.properties['Date'].getMonth()]); 
  var values = inven_wks.getDataRange().getValues();
  var hdr = values[0];

  for(var i=0; i<hdr.length; i++) {
    hdr[i] = hdr[i].trim();
  }
  
  if(!inven_wks) {
    Browser.msgBox(
      'No Inventory Sheet for ' + MONTHS[route.properties['Date'].getMonth()],
      Browser.Buttons.OK);
    return;
  }
  
  var to_row = START_ROW;
  while (to_row - 1 < values.length) {
    if(!values[to_row - 1])
      break;
    to_row++;
  }
  
  var row = new Array(hdr.length);
  for(var i=0; i<row.length; i++)
    row[i] = '';
 
  row[hdr.indexOf('Date')] = route.properties['Date'];
  row[hdr.indexOf('Driver')] = route.properties['Driver'];
  row[hdr.indexOf('Block')] = route.properties['Block'];
  
  for(var key in route.inventory) {
    row[hdr.indexOf(key)] = route.inventory[key];
  }
  
  inven_wks.getRange(to_row,1,1,row.length).setValues([row]);
}

//---------------------------------------------------------------------
function updateVecStats(route, stats_ss_id) {
 
  var stats_ss = SpreadsheetApp.openById(stats_ss_id);
  var stats_wks = stats_ss.getSheetByName('Daily');  
  var stats_hdr = stats_wks.getRange(1,1,1,stats_wks.getMaxColumns()).getValues()[0];
  var row_val = new Array(stats_wks.getMaxColumns());
  var max_rows = stats_wks.getMaxRows()+1;
  for(var i=0; i<row_val.length; i++)
    row_val[i] = '';
  
  for(var key in route.properties) {
    if(stats_hdr.indexOf(key) > -1)
      row_val[stats_hdr.indexOf(key)] = route.properties[key];
  }
  
  row_val[stats_hdr.indexOf('Y')]                  = route.properties['Date'].getFullYear();
  row_val[stats_hdr.indexOf('M')]                  = MONTHS[route.properties['Date'].getMonth()];
  row_val[stats_hdr.indexOf('D')]                  = route.properties['Date'].getDate();
  row_val[stats_hdr.indexOf('Trip Lgth Actual')]   = route.properties['Trip Hrs'];
  row_val[stats_hdr.indexOf('Trip Lgth Sched')]   = route.properties['Trip Lgth Sched']/60;
  
  stats_wks.getRange(
    max_rows,
    1,
    1,
    row_val.length)
  .setValues([row_val]);
  
  stats_wks.getRange(
    max_rows,
    stats_hdr.indexOf('Estmt Margin [±]')+2,
    1, 
    1)
  .setFormula('=if(isnumber(R[0]C[5]),(R[0]C[-1] - R[0]C[5]) / R[0]C[5], "-")');
}
