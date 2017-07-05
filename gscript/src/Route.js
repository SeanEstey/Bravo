function Route(){}

//---------------------------------------------------------------------
function Route(group, ss_id) {
  /* Object containing data and properties from a route SS

  */
  
  this.group = group;
  this.ss_id = ss_id;
  this.ss = SpreadsheetApp.openById(ss_id);
  this.getOrders();
  this.getInfoProperties();
  this.getInventory();
}

//---------------------------------------------------------------------
Route.prototype.getOrders = function() {
  /* this.orders: 2D array of values. Excludes Depot, Office stops
  */
  
  var orders_wks = this.ss.getSheetByName("Orders");
  var values = orders_wks.getDataRange().getValues();
  
  this.orders_hdr = values[0];
  this.orders = values.filter(getIdFilter(values[0].indexOf('ID')));
}

//---------------------------------------------------------------------
Route.prototype.getInfoProperties = function() {
  
  var info_wks = this.ss.getSheetByName("Info");
  
  var values = info_wks.getRange(
    2, 
    1,
    info_wks.getMaxRows(),
    info_wks.getMaxColumns())
  .getValues();
  
  this.properties = {};
  
  for(var i=0; i<values.length; i++) {
    // TODO: what about duplicate values from multiple drivers?
    this.properties[values[i][0]] = values[i][1];
  }
}

//---------------------------------------------------------------------
Route.prototype.getInventory = function() {
  
  var inven_wks = this.ss.getSheetByName("Inventory");
  
  if(inven_wks == null)
    return;
  
  var values = inven_wks.getRange(
    2, 
    1,
    inven_wks.getMaxRows(),
    inven_wks.getMaxColumns())
  .getValues();
  
  this.inventory = {};
  
  for(var i=0; i<values.length; i++) {
    if(values[i][0].search("Select") == -1)
      this.inventory[values[i][0]] = values[i][1];
  }
}

//---------------------------------------------------------------------
Route.prototype.orderToDict = function(idx) {
  /* Converts row array from route into key/value dictionary
   */
  
  if(idx >= this.orders.length)
    return false;
  
  var order_info = this.getOrderValue(idx,'Order Info');
  var act_name_regex = /Name\:\s(([a-zA-Z]*?\s)*){1,5}/g;
  var account_name = '';
      
  // Parse Account Name from "Order Info" string
  if(act_name_regex.test(order_info))
    account_name = order_info.match(act_name_regex)[0];   
  
  var gift = false;
  if(isNumber(this.orders[idx][this.orders_hdr.indexOf('$')]))
     gift = Number(this.orders[idx][this.orders_hdr.indexOf('$')]);
    
  return {
    'ID': this.getOrderValue(idx,'ID'),
    'Address': this.getOrderValue(idx, 'Address') || '',
    'Account': account_name + this.getOrderValue(idx,'Address'),
    'Estimate': gift,
    'Notes': (this.getOrderValue(idx,'Notes') || ''),
    'Driver Notes': (this.getOrderValue(idx,'Driver Notes') || ''),
    'Block': this.getOrderValue(idx,'Block').replace(/, /g, ','),
    'Neighborhood': (this.getOrderValue(idx,'Neighborhood') || '').replace(/, /g, ','),
    'Status': this.getOrderValue(idx,'Status'),
    'Office Notes': (this.getOrderValue(idx,'Office Notes') || '')
  }
}

//---------------------------------------------------------------------
Route.prototype.getBlockType = function() {
  if(Parser.isRes(this.properties['Block']))
     return 'Res';
  else if(Parser.isBus(this.properties['Block']))
    return 'Bus';
}

//---------------------------------------------------------------------
Route.prototype.getOrderValue = function(order_idx, column_name) {
  return this.orders[order_idx][this.orders_hdr.indexOf(column_name)] || false;
}

//---------------------------------------------------------------------
function getIdFilter(col_idx) {  
  return function(element) {
    return isNumber(element[col_idx]);
  }
}
