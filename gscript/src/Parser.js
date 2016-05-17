function Parser() {}

// Bus Block title prefixed with 'B', 6 week cycle: 'B5A', 'B4D', 'B6E'
Parser['bus_block_regex'] = /^B[1-6]{1}[A-E]{1}$/g;

// Res Block title prefixed with 'R', numbered 1-10: 'R5A', 'R6H', 'R10P'
Parser['res_block_regex'] = /^R([1-9]|10)[a-zA-Z]{1}$/g;

// Either Bus or Res Block
Parser['block_regex'] = /(B|R)\d{1,2}[a-zA-Z]{1}/g;

// Comma-separated list of blocks: 'B4A, R2M, R5S'
Parser['block_list_regex'] = /^(,?\s*(B|R)\d{1,2}[a-zA-Z]{1})*$/g;


Parser.isRes = function(block) { return block.match(Parser['res_block_regex']); }

Parser.isBus = function(block) { return block.match(Parser['bus_block_regex']); }

Parser.isBlockList = function(blocks) { return blocks.match(Parser['block_list_regex']); }

Parser.isBlock = function(block) { return (Parser.isRes(block) || Parser.isBus(block)); }

Parser.isPostalCode = function(value) {
  return (value.match(/^T\d[A-Z]$/i) || value.match(/^T\d[A-Z] \d[A-Z]\d$/i));
}

Parser.isAccountId = function(value) { return value.match(/^[\/]?[0-9]{1,6}$/); }

Parser.getBlockFromTitle = function(title) {  
  /* title: can be a route title: "Dec 27: R7E (Ryan)" 
   * or calendar event name: "R5D [Twin Brooks] (72/74)"
   */
  
  if(Parser['block_regex'].test(title))
    return title.match(Parser['block_regex'])[0];
  else
    return false;
}

Parser.getBlockSize = function(title) {
  /* title: calendar event name. Returns left number in "B5A [] (25/30)"
   * or '?' if name doesn't contain block size
   */
  
  if(title[0] == 'B')
    return '?';
    
  if(title.indexOf('/') > -1)
    return title.slice(title.indexOf("/")+1, -1);
  else
    return '?';
}

Parser.getBookingSize = function(title) {
  // Bus run
  if(title[0] == 'B') {
    if(title.indexOf('(') > 0)
      return title.slice(title.indexOf('(')+1, title.indexOf('/'));
    else
      return '?';
  }
  
  // Res run 
  if(title.indexOf('/') > -1)
    return title.slice(title.indexOf('(')+1,title.indexOf('/'));
  else
    return '?';
}