//---------------------------------------------------------------------
function findRow(wks, block) {
  
  var hdr = wks.getRange(1,1,1,wks.getMaxColumns()).getValues()[0];
  var idx = 0;
  var values = wks.getRange(
    1,
    hdr.indexOf('Block') + 1,
    wks.getMaxRows(),
    wks.getMaxColumns())
  .getValues();

  while (idx < values.length) {
    if(String(values[idx]).indexOf(block) > -1)
      return idx + 1;
    idx++;
  }
}

//---------------------------------------------------------------------
function updateWsfStats(route, stats_ss_id, archv_ss_id) {

  var ss = SpreadsheetApp.openById(stats_ss_id);
  var stats_wks;
  var row;
  var blk_type = route.getBlockType();
  var month = MONTHS[route.properties['Date'].getMonth()];

  while(!stats_wks) {
    var wks = ss.getSheetByName(month + ' ' + blk_type);
    row = findRow(wks, route.properties['Block']);
    
    if(row) {
      stats_wks = wks;
    }
    else {  
      // Try next month (carry-over)       
      if(month == 'Dec')
        month = 'Jan';
      else
        month = MONTHS[MONTHS.indexOf(month)+1];
    }
  }
  
  if(!stats_wks) {
    Browser.msgBox(
      'No Stats Sheet for ' + MONTHS[route.properties['Date'].getMonth()],
      Browser.Buttons.OK);
    return false;
  }
  
  Logger.log("stats_wks name: " + stats_wks.getName());
  
  var values = stats_wks.getRange(row,1,1,stats_wks.getLastColumn()).getValues()[0];
  var hdr = stats_wks.getRange(1,1,1,stats_wks.getMaxColumns()).getValues()[0];    
  var prop = route.properties;
  
  values[hdr.indexOf('Date')]             = prop['Date'];
  values[hdr.indexOf('Block')]            = prop['Block'];
  values[hdr.indexOf('Estimate')]         = prop['Total'];
  values[hdr.indexOf('Driver')]           = prop['Driver'];
  values[hdr.indexOf('Size')]             = prop['Orders'];
  values[hdr.indexOf('New')]              = prop['Dropoffs'];
  values[hdr.indexOf('Zero')]             = prop['Zeros'];
  values[hdr.indexOf('Gifts')]            = prop['Participants'];
  values[hdr.indexOf('Part')]             = prop['%']; // FIXME. Calculate core participation
  values[hdr.indexOf('Hrs')]              = prop['Driver Hrs'];  
  values[hdr.indexOf('Depot')]            = prop['Depot'];
  values[hdr.indexOf('Projected')]        = prop['Vehicle'] + ': ' + 
                                            prop['Inspection'] + 
                                            ' Mileage: ' + prop['Mileage'] + 
                                            '\nNotes: ' + prop['Notes'];
  
  var archv_wks = SpreadsheetApp.openById(archv_ss_id)
    .getSheetByName('Residential');
 
  if(findRow(archv_wks, route.properties['Block'])) {
    var archv_hdr = archv_wks.getRange(
      1, 1,
      1, archv_wks.getMaxColumns())
    .getValues()[0];
    
    var archv_values = archv_wks.getRange(
      findRow(archv_wks, route.properties['Block']), 1,
      1, archv_wks.getLastColumn())
    .getValues()[0];
    
    values[hdr.indexOf('Last Part')] = archv_values[archv_hdr.indexOf('Part')];
    values[hdr.indexOf('Last Receipt')] = archv_values[archv_hdr.indexOf('Receipt')];
    values[hdr.indexOf('Part Diff')] = archv_values[hdr.indexOf('Part')] - archv_values[hdr.indexOf('Last Part')];
  }
  
  stats_wks.getRange(row,1,1,values.length).setValues([values]);
  
  /*************** FORMULAS ********************/
  
  // If < 1L field has value, calculate receipt $ amount
  var receipt_formula = '=if(ISNUMBER(R[0]C[-2]), (0.1*R[0]C[-2])+(0.25*R[0]C[-1]),"")';
  stats_wks.getRange(row, hdr.indexOf('Receipt')+1, 1, 1).setFormula(receipt_formula);
  
  if(blk_type == 'Res') {      
    // If Receipt & Last Receipt fields have values, subtract Last Receipt from Receipt
    var receipt_diff_formula = '=if(and(ISNUMBER(R[0]C[-2]),ISNUMBER(R[0]C[-1])),R[0]C[-2] - R[0]C[-1], "-")';
    
    // If Receipt, calculate % estimate error
    var estimate_diff_formula = '=if(isnumber(R[0]C[-4]),(R[0]C[-1] - R[0]C[-4]) / R[0]C[-4], "-")';
    
    stats_wks.getRange(row, hdr.indexOf('Receipt Diff')+1, 1, 1).setFormula(receipt_diff_formula);
    stats_wks.getRange(row, hdr.indexOf('Estimate Diff')+1, 1, 1).setFormula(estimate_diff_formula);
  }
  
  if(values[hdr.indexOf('Part Diff')] < 0)
    stats_wks.getRange(row, hdr.indexOf('Part Diff'), 1, 3).setFontColor('#e06666');
  else if(values[hdr.indexOf('Part Diff')] > 0)
    stats_wks.getRange(row, hdr.indexOf('Part Diff')+1, 1, 3).setFontColor('#6aa84f');  
}

