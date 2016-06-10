//---------------------------------------------------------------------
function findStatsEntryRow(sheet, block) {
  var route_names = sheet.getRange("A1:$A").getValues();
  
  var row_ind = 0;
  
  while (row_ind < route_names.length) {
    if(String(route_names[row_ind]).indexOf(block) > -1)
      return row_ind;
    row_ind++;
  }
  return false;
}

//---------------------------------------------------------------------
function updateStats(ss_id, archive_ss_id, route) {
  try {
    var ss = SpreadsheetApp.openById(ss_id);
    
    var month = route.title.substring(0,3);
    var route_type;
    
    if(Parser.isRes(route.title_block))
      route_type = 'Res';
    else if(Parser.isBus(route.title_block))
      route_type = 'Bus';
    
    var sheet = ss.getSheetByName(month + ' ' + route_type);
    
    if(!sheet) {
      Browser.msgBox('Cannot find Stats sheet: ' + month + ' ' + route_type, Browser.Buttons.OK);
      return false;
    }
    
    var row_index = findStatsEntryRow(sheet, route.title_block);
    
    // Try next month (carry-over)
    if(!row_index) {
      if(month == 'Dec')
        month = 'Jan';
      else
        month = route.months[route.months.indexOf(month)+1];

      sheet = ss.getSheetByName(month + ' ' + route_type);
      
      row_index = findStatsEntryRow(sheet, route.title_block);
      if(!row_index) {
        log('Stats entry not found for block ' + route.title_block);
        return false;
      }
    }
    
    var stats_row = sheet.getRange(row_index+1,1,1,sheet.getLastColumn()).getValues()[0];
    var headers = sheet.getRange(1,1,1,sheet.getMaxColumns()).getValues()[0];
      
    if(route_type == 'Res') {
      var num_dropoffs = 0;
      var num_zeros = 0;
      var num_core_gifts = 0;
      
      for(var i=0; i<route.orders.length; i++) {      
        if(route.getValue(i,'Status') == 'Dropoff')
          num_dropoffs++;
        else {
          if(route.getValue(i,'$') == 0)
            num_zeros++;
          else if(route.getValue(i,'$') > 0)
            num_core_gifts++;
        }
      }
      
      stats_row[headers.indexOf('Size')] = route.orders.length;
      stats_row[headers.indexOf('New')] = num_dropoffs;
      stats_row[headers.indexOf('Zero')] = num_zeros;
      stats_row[headers.indexOf('Part')] = (num_core_gifts) / (route.orders.length - num_dropoffs);
      var str_part = String(Math.floor(stats_row[headers.indexOf('Part')]*100)) + '% ';
        
      var archive_ss = SpreadsheetApp.openById(archive_ss_id);
      var archive_sheet = archive_ss.getSheetByName('Residential');
      var prev_stats_index = findStatsEntryRow(archive_sheet, route.title_block);
      
      Logger.log('prev_route_archive_row_index: ' + prev_stats_index);
      
      var archive_headers = archive_sheet.getRange(1,1,1,archive_sheet.getMaxColumns()).getValues()[0];
      
      if(prev_stats_index) {
        var prev_stats_row = archive_sheet.getRange(prev_stats_index+1,1,1,archive_sheet.getLastColumn()).getValues()[0];
        Logger.log('prev_stats_row: ' + prev_stats_row);
        stats_row[headers.indexOf('Last Part')] = prev_stats_row[archive_headers.indexOf('Part')];
        stats_row[headers.indexOf('Last Receipt')] = prev_stats_row[archive_headers.indexOf('Receipt')];
        stats_row[headers.indexOf('Part Diff')] = stats_row[headers.indexOf('Part')] - stats_row[headers.indexOf('Last Part')];
      }
    }
    
    var info = route.getInfo();

    // Notes go in 'Projected' column on Stats Sheet
    stats_row[headers.indexOf('Projected')] = '';
    if(info['Notes'].length > 0)
      stats_row[headers.indexOf('Projected')] += "Notes: " + info['Notes'] + "\n";
    if(info['Vehicle Inspection'].length > 0)
      stats_row[headers.indexOf('Projected')] += "Truck: " + info['Vehicle Inspection'] + ". ";
    if(info['Mileage'].length > 0)
      stats_row[headers.indexOf('Projected')] += "Mileage: " + info['Mileage'];
    if(info['Garage ($)'].length > 0)
      stats_row[headers.indexOf('Projected')] += 'Garage: ' + info['Garage ($)'];
    
    stats_row[headers.indexOf('Gifts')] = info['Participants'];
    stats_row[headers.indexOf('Part')] = info['%'];
    stats_row[headers.indexOf('Estimate')] = info['Total'];
    stats_row[headers.indexOf('Driver')] = route.driver; 
    stats_row[headers.indexOf('Hrs')] = info['Driver Hours']; 
    stats_row[headers.indexOf('Depot')] = info['Depot'];
    stats_row[headers.indexOf('Trip Info')] = info['Info'];
    
    // Write row values
    sheet.getRange(row_index+1,1,1,stats_row.length).setValues([stats_row]);
    
    /*************** FORMULAS ********************/
    
    // If < 1L field has value, calculate receipt $ amount
    var receipt_formula = '=if(ISNUMBER(R[0]C[-2]), (0.1*R[0]C[-2])+(0.25*R[0]C[-1]),"")';
    sheet.getRange(row_index+1, headers.indexOf('Receipt')+1, 1, 1).setFormula(receipt_formula);
     
    if(route_type == 'Res') {      
      // If Receipt & Last Receipt fields have values, subtract Last Receipt from Receipt
      var receipt_diff_formula = '=if(and(ISNUMBER(R[0]C[-2]),ISNUMBER(R[0]C[-1])),R[0]C[-2] - R[0]C[-1], "-")';
      
      // If Receipt, calculate % estimate error
      var estimate_diff_formula = '=if(isnumber(R[0]C[-4]),(R[0]C[-1] - R[0]C[-4]) / R[0]C[-4], "-")';
      
      sheet.getRange(row_index+1, headers.indexOf('Receipt Diff')+1, 1, 1).setFormula(receipt_diff_formula);
      sheet.getRange(row_index+1, headers.indexOf('Estimate Diff')+1, 1, 1).setFormula(estimate_diff_formula);
    }
    
    if(stats_row[headers.indexOf('Part Diff')] < 0)
      sheet.getRange(row_index+1, headers.indexOf('Part Diff'), 1, 3).setFontColor('#e06666');
    else if(stats_row[headers.indexOf('Part Diff')] > 0)
      sheet.getRange(row_index+1, headers.indexOf('Part Diff')+1, 1, 3).setFontColor('#6aa84f');  
  }
  catch(e) {
    var msg = 
      route.title_block + ' update stats failed.\\n' +
      'Msg: ' + e.message + '\\n' +
      'File: ' + e.fileName + '\\n' + 
      'Line: ' + e.lineNumber;    
      log(msg, true);
    SpreadsheetApp.getUi().alert(msg);
  }
  finally {
    log(route.title + ' added to stats sheet', true);
  }
}

//---------------------------------------------------------------------
function updateInventory(ss_id, route) {
  try {
    var ss = SpreadsheetApp.openById(ss_id);
    var sheet = ss.getSheetByName(route.months[route.date.getMonth()]); 
    
    var rows = sheet.getDataRange().getValues();
    var headers = rows[0];
    var entries = rows.slice(3);
        
    if(!sheet) {
      log('No inven sheet for ' + route.months[route.date.getMonth()], true);
      return;
    }
    
    // Find dest Inventory row
    var dest_row=7;
    while (dest_row - 1 < rows.length) {
      if(!rows[dest_row - 1])
        break;
      dest_row++;
    }
    
    var signed_out = route.getInventoryChanges();
    
    // Format for write to Inventory sheet
    var row = new Array(headers.length);
    
    for(var i=0; i<row.length; i++)
      row[i] = '';
   
    row[headers.indexOf('Date')] = route.date;
    row[headers.indexOf('Bag Buddies')] = signed_out['Bag Buddies In'];  
    row[headers.indexOf('Bag Buddies')+1] = signed_out['Bag Buddies Out'];
    row[headers.indexOf('Green Bags')] = signed_out['Green Bags'];
    row[headers.indexOf('Green Logo Bags')] = signed_out['Green Logo Bags'];
    row[headers.indexOf('White Bags')] = signed_out['White Bags'];
    row[headers.indexOf('Green Bins')] = signed_out['Green Bins Out']; 
    row[headers.indexOf('Green Bins')+1] = signed_out['Green Bins In'];
    row[headers.indexOf('Blue Bins')] = signed_out['Blue Bins Out'];
    row[headers.indexOf('Blue Bins')+1] = signed_out['Blue Bins In'];
    row[headers.indexOf('Bottle Bins')] = signed_out['Bottle Bins In'];
    row[headers.indexOf('Bottle Bins')+1] = signed_out['Bottle Bins Out'];
    row[headers.indexOf('Driver')] = route.driver;
    row[headers.indexOf('Block')] = route.title_block;
    
    sheet.getRange(dest_row,1,1,row.length).setValues([row]);
  }
  catch(e) {
    var msg = 
      route.title_block + ' update inventory failed.\\n' +
      'Msg: ' + e.message + '\\n' +
      'File: ' + e.fileName + '\\n' + 
      'Line: ' + e.lineNumber;    
    log(msg, true);
    SpreadsheetApp.getUi().alert(msg);
  }
  finally {
    log(route.title + ' added to inventory sheet', true);
  }
}


//------------------------------------------------------------------------------
function calculateEstimateError() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var estimate_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Estimate') + 1;
  var receipt_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Receipt') + 1;
  var rows = sheet.getDataRange();
  var estimate_values = sheet.getRange(3, estimate_col, rows.getNumRows(), 1).getValues();
  var receipt_values = sheet.getRange(3, receipt_col, rows.getNumRows(), 1).getValues();
  var diff = 0;
  
  for(var i=0; i<receipt_values.length; i++) {
    if(Number(receipt_values[i]) > 0 && Number(estimate_values[i]) > 0)
      diff += Number(estimate_values[i]) - Number(receipt_values[i]);
  }
  
  var estimateError = diff / Number(sheet.getRange(2, receipt_col).getValue());
  var estimateDiffCol = sheet.getRange("A1:Y1").getValues()[0].indexOf('Estimate Diff') + 1;
  sheet.getRange(2, estimateDiffCol).setValue(estimateError);
  Logger.log('Updated estimate error');
}

//------------------------------------------------------------------------------
function projectMonthlyRevenue() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var rows = sheet.getDataRange();
  var estimate_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Estimate') + 1;
  var receipt_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Receipt') + 1;
  var last_receipt_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Last $') + 1;
  var titleColumn = sheet.getRange("A3:A").getValues();
  var estimate_values = sheet.getRange(3, estimate_col, rows.getNumRows()-2, 1).getValues();
  var receipt_values = sheet.getRange(3, receipt_col, rows.getNumRows()-2, 1).getValues();
  
  
  if(last_receipt_col == 0)
    var last_receipt_values = null;
  else
    var last_receipt_values = sheet.getRange(3, last_receipt_col, rows.getNumRows()-2, 1).getValues();
  var avg_receipt_col = sheet.getRange("A1:Y1").getValues()[0].indexOf('Avg Receipt') + 1;
  var avgReceipt = Number(sheet.getRange(2, avg_receipt_col).getValue());
  var projectedRevenue = 0;
  
  for(var i=0; i<receipt_values.length; i++) {
  // if(titleColumn[i].indexOf("Dropoff") >= 0)
  //   continue;
    
    if(Number(receipt_values[i]) > 0) {
      projectedRevenue += Number(receipt_values[i]);
      Logger.log('Adding receipt ' + Number(receipt_values[i]));
    }
    else if(Number(estimate_values[i]) > 0) {
      projectedRevenue += Number(estimate_values[i]);
      Logger.log('Adding estimate ' + Number(estimate_values[i]));
    }
    else {
      projectedRevenue += Number(avgReceipt);
      Logger.log('Adding avg ' + Number(avgReceipt));
    }
  }
    
  var projectedRevCol = sheet.getRange("A1:Y1").getValues()[0].indexOf('Projected') + 1;
  sheet.getRange(2, projectedRevCol).setValue(Number(projectedRevenue.toFixed(0)));
  Logger.log('Updated projected revenue: ' + Number(projectedRevenue.toFixed(0)));
}

//------------------------------------------------------------------------------
function clearResidentialRun() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var rows = sheet.getDataRange();
  var numRows = rows.getNumRows();
  var values = rows.getValues();  // 2d array
  
  var headers = values[0];
  
  sheet.getRange(3,1, numRows-2,1).clear();  // Run name
  sheet.getRange(3,headers.indexOf('Date')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Size')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('New')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Part')+1, numRows-2, 1).clear();  
  sheet.getRange(3,headers.indexOf('< 1L')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('> 1L')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Estimate')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Last $')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Driver')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Hrs')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('MPU')+1, numRows-2, 1).clear();
  sheet.getRange(3,headers.indexOf('Projected Revenue:')+1, numRows-2, 1).clear();
  sheet.getRange(3, headers.length, numRows-2, 1).clear();   // Header is generated automatically for mileage, so find last column
}