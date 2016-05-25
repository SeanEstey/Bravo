//---------------------------------------------------------------------
function Route(id) {
  this.id = id;
  this.ss = SpreadsheetApp.openById(id);
  this.sheet = this.ss.getSheets()[0];
  
  var data = this.sheet.getDataRange().getValues();
  
  this.headers = data.slice(0,1)[0];
  
  var num_orders = this.sheet.getRange("E1:E")
    .getValues().filter(String).length - 1;
  
  // Order rows excluding last Depot row
  this.orders = data.slice(1, num_orders + 1);
  
  // Route title format: "Dec 27: R4E (Ryan)"
  this.title = this.ss.getName();
  this.title_block = Parser.getBlockFromTitle(this.title);
     
  var date_str = this.title.substring(0, this.title.indexOf(":"));
  var full_date_str = date_str + ", " + (new Date()).getFullYear();
  this.date = new Date(full_date_str);
  this.driver = this.title.substring(
    this.title.indexOf("(")+1, 
    this.title.indexOf(")")
  );
   
  Logger.log('New Route block: ' + this.title_block);
    
  this.months = [
    "Jan", 
    "Feb", 
    "Mar", 
    "Apr", 
    "May", 
    "Jun", 
    "Jul", 
    "Aug", 
    "Sep", 
    "Oct", 
    "Nov", 
    "Dec"
  ];
}

//---------------------------------------------------------------------
Route.prototype.getValue = function(order_idx, column_name) {
  return this.orders[order_idx][this.headers.indexOf(column_name)] || '';
}

//---------------------------------------------------------------------
Route.prototype.orderToDict = function(idx) {
  /* For RouteProcessor processing */
  
  if(idx >= this.orders.length)
    return false;
  
  var order_info = this.getValue(idx,'Order Info');
  var act_name_regex = /Name\:\s(([a-zA-Z]*?\s)*){1,5}/g;
  var account_name = '';
      
  // Parse Account Name from "Order Info" string
  if(act_name_regex.test(order_info))
    account_name = order_info.match(act_name_regex)[0] + '\n';    
    
  return {
    'Account Number': this.getValue(idx,'ID'),
    'Name & Address': account_name + this.getValue(idx,'Address'),
    'Gift Estimate': this.getValue(idx,'$'),
    'Driver Input': this.getValue(idx,'Notes'),
    'Driver Notes': this.getValue(idx,'Driver Notes'),
    'Block': this.getValue(idx,'Block').replace(/, /g, ','),
    'Neighborhood': this.getValue(idx,'Neighborhood').replace(/, /g, ','),
    'Status': this.getValue(idx,'Status'),
    'Office Notes': this.getValue(idx,'Office Notes')
  }
}

//---------------------------------------------------------------------
Route.prototype.getInfo = function() { 
  /* Gather Stats and Inven fields from bottom section of Route, build 
   * dictionary
   * Returns: Dict object on success, false on error
   */
  
  var a = this.sheet.getRange(
    this.orders.length+3,
    1,
    this.sheet.getMaxRows()-this.orders.length+1,
    1).getValues();

  // Make into 1D array of field names: ["Total", "Participants", ...]
  a = a.join('//').split('//');
   
  var start = a.indexOf('***Route Info***');
  
  if(start < 0)
    return false;
  else
    start++;
  
  a.splice(0, start);
  
  var inven_idx = a.indexOf('***Inventory***');
  
  if(inven_idx < 0)
    return false;
  
  // Now left with Stats and Inventory field names
  
  stats_fields = a.splice(0, inven_idx);
  
  var stats = {};
  
  var b = this.sheet.getRange(
    this.orders.length+3,
    2,
    this.sheet.getMaxRows()-this.orders.length+1,
    1).getValues();
  
  b.splice(0, start);
  
  for(var i=0; i<stats_fields.length; i++) {
    var key = stats_fields[i]; 
    stats[key] = b[i][0];
  }
  
  return stats;
}

//---------------------------------------------------------------------
Route.prototype.getInventoryChanges = function() {
  var a = this.sheet.getRange(1,1,this.sheet.getMaxRows(),1).getValues();
  var b = this.sheet.getRange(1,2,this.sheet.getMaxRows(),1).getValues();
  
  a = a.join('//').split('//');
  b = b.join('//').split('//');
  
  var inven_idx = a.indexOf('***Inventory***');
  
  if(inven_idx < 0)
    return false;
  
  a = a.slice(inven_idx + 1, a.length);
  b = b.slice(inven_idx + 1, b.length);

  /* TODO: Loop through spliced array, make dictionary of all fields and values without referencing them by name below */
  
  return {
    'Bag Buddies In': b[a.indexOf('Bag Buddies In')],
    'Bag Buddies Out': b[a.indexOf('Bag Buddies Out')],
    'Green Bags': b[a.indexOf('Green Bags')],
    'Green Logo Bags': b[a.indexOf('Green Logo Bags')],
    'White Bags': b[a.indexOf('White Bags')],
    'Green Bins In': b[a.indexOf('Green Bins In')],
    'Green Bins Out': b[a.indexOf('Green Bins Out')],
    'Blue Bins In': b[a.indexOf('Blue Bins In')],
    'Blue Bins Out': b[a.indexOf('Blue Bins Out')],
    'Bottle Bins In': b[a.indexOf('Bottle Bins In')],
    'Bottle Bins Out': b[a.indexOf('Bottle Bins Out')]
  };
}