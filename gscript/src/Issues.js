//---------------------------------------------------------------------
function uploadIssue(conf) {
  
  var wks = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var active_range = wks.getActiveRange();
  var row = active_range.getRow();
  var row_val = active_range.getValues()[0];
  var wks_hdr = wks.getRange(1, 1, 1, wks.getMaxColumns()).getValues()[0];
  
  var status = (row_val[wks_hdr.indexOf('Resolved')] == "No" ? "OPEN" : "CLOSED");
  var update_fields = {
    "Block": row_val[wks_hdr.indexOf("Block")],
    "Neighborhood": row_val[wks_hdr.indexOf("Neighborhood")],
    "Status": row_val[wks_hdr.indexOf("Status")],
    "Driver Notes": row_val[wks_hdr.indexOf("Driver Notes")],
    "Office Notes": row_val[wks_hdr.indexOf("Office Notes")],
    "Next Pickup Date": date_to_ddmmyyyy(row_val[wks_hdr.indexOf("Next Pickup")])
  };
  
  for(var k in update_fields) {
    if(!update_fields[k])
      delete update_fields[k];
  }
  
  var ref = null;
  if(wks.getRange(row,1,1,1).getValue() == SYMBOL['checkmark'])
    ref = wks.getRange(row, 1, 1, 1).getNote();
  
  var rv = API(
    "/accounts/save_rfu",
    conf, {
      "ref": ref, //row_val[wks_hdr.indexOf("Ref")],
      "acct_id": String(row_val[wks_hdr.indexOf("ID")]),
      "date": date_to_ddmmyyyy(row_val[wks_hdr.indexOf('Date')]),
      "body": 
        "Issue: " + row_val[wks_hdr.indexOf('Type')] + '\n'+
        "Description:\n" + row_val[wks_hdr.indexOf('Description')] +"\n"+
        "Comments:\n" + row_val[wks_hdr.indexOf('Comments')] +"\n"+
        "Author: " + row_val[wks_hdr.indexOf('Initials')] +"\n"+
        "Status: " + status,     
      "fields": JSON.stringify(update_fields)});
         
  if(rv.hasOwnProperty("ref")) {
    if(status == 'CLOSED') {
      Logger.log('RFU Resolved. Clearing row');
      wks.deleteRow(row); 
    }
    else {
      Logger.log("Received Ref=" + rv["ref"] + ". Updating wks...");
      wks.getRange(row, 1, 1, 1).setNote(rv["ref"]);
      wks.getRange(row, 1, 1, 1).setValue(SYMBOL["checkmark"]);
      wks.getRange(row, 1, 1, 1).setFontColor(COLOR['green']); 
    }
  }
  else {
    wks.getRange(row, 1, 1, 1).setNote(rv);
    wks.getRange(row, 1, 1, 1).setValue(SYMBOL["x"]);
    wks.getRange(row, 1, 1, 1).setFontColor(COLOR['light red']); 
  }
}
