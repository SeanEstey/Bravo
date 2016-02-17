<?php

require("./lib/nusoap.php");

function connect($db) {
  if($db->connect_errno > 0){
    die('Unable to connect to database [' . $db->connect_error . ']');
  }
}


function checkForError($nsc) {
  if($nsc->fault || $nsc->getError()) {
    if(!$nsc->fault) {
      error_log("Error: " . $nsc->getError());
      return true;
    }
    else {
      error_log("Fault Code: " . $nsc->faultcode);
      error_log("Fault String: " .$nsc->faultstring);
      http_response_code(400);  
      return true;
    }
  }

  return false;
}

//-----------------------------------------------------------------------
function formatDateAsDateTimeString($dateStr) {
  if ($dateStr == null || $dateStr == "") return "";
  if (substr_count($dateStr, "/") != 2) return "[Invalid Date: $dateStr]";

  $separator1 = stripos($dateStr, "/");
  $separator2 = stripos($dateStr, "/", $separator1 + 1);

  $day = substr($dateStr, 0, $separator1);
  $month = substr($dateStr, $separator1 + 1, $separator2 - $separator1 - 1);
  $year = substr($dateStr, $separator2 + 1);

  if($day > 0 && $month > 0 && $year > 0)
    return date(DATE_ATOM, mktime(0, 0, 0, $month, $day, $year));
  else
    return "[Invalid Date: $dateStr]";
}

//-----------------------------------------------------------------------
function get_account($nsc, $account_number) {
  $account = $nsc->call("getAccountById", array($account_number));
  
  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    http_response_code(400);
    return false;
  }

  http_response_code(200);
  return $account;
}

//-----------------------------------------------------------------------
/* Returns amount of stops on specific date */
function get_scheduled_run_size($nsc, $query_category, $query, $date) {
  ini_set('max_execution_time', 3000); // IMPORTANT: To prevent fatail error timeout
  
  $response = $nsc->call("getExistingQueryResults", [[ 
    'start' => 0,
    'count' => 500,
    'query' => "$query_category::$query"
  ]]);

  // Fault Code 102: Invalid Query Category
  // Fault Code 103: Invalid Query
  if(checkForError($nsc)) {
    http_response_code(400);
    echo $response['faultstring'];
    return false;
  }
  
  $matches = 0;
  foreach($response['data'] as $account) {
    foreach($account['accountDefinedValues'] as $udf) {
      if($udf['fieldName'] == 'Next Pickup Date' && $date == $udf['value']) {
        $matches++;
        break;
      }
    }
  }

  $ratio = (string)$matches . '/';

  if(isset($response['count']))
    $ratio .= (string)$response['count'];
  else
    $ratio .= '?';
  
  write_log($query . ': ' . $ratio);
  echo $ratio;

  http_response_code(200);
}

//-----------------------------------------------------------------------
function get_block_size($nsc, $query_category, $query) {
  $response = $nsc->call('getExistingQueryResults', [[
    'start' => 0,
    'count' => 500,
    'query' => "$query_category::$query"
    ]]
  );

  if(checkForError($nsc)) {
    echo $response;
    return false; 
  }

  // Next P/U Date returns in dd/mm/yyyy format
  write_log('Query ' . $query . ' count: ' . $response['count']);
  echo $response['count'];
  http_response_code(200);  
}

// Returns all Gifts with amount > $0 between given dates
//-----------------------------------------------------------------------
function get_gift_history($nsc, $ref, $start_date, $end_date) {
  ini_set('max_execution_time', 3000); // IMPORTANT: To prevent fatail error timeout

  //$account = $nsc->call('getAccountById', [$account_number]);

  // Return filtered journal entries for provided year
  $request = [
    'accountRef' => $ref,
    'start' => 0,
    'count' => 100,
    'startDate' => formatDateAsDateTimeString($start_date),
    'endDate' => formatDateAsDateTimeString($end_date),
    'types' => [5] // Gifts filter
    ];

  $response = $nsc->call("getJournalEntries", array($request));
  
  checkForError($nsc);

  $gifts = [];

  for($i=0; $i<$response['count']; $i++) {
    $entry = $response['data'][$i];

    if($entry['campaign'] != 'Empties to WINN')
      continue;

    if($entry['amount'] > 0) {
      $gifts[] = [
        'amount' => $entry['amount'],
        'date' => $entry['date']
        ];
    }
  }

  return $gifts;
}


//-----------------------------------------------------------------------
/* Check on progress of update_accounts, add_gifts, add_accounts */
function get_upload_status($db, $request_id, $from_row) {
  
  $cursor = $db->find(['request_id'=>$request_id]);
  $results = [];

  foreach($cursor as $document) {
    $array = get_object_vars($document);
    unset($array['_id']);
    $results[] = $array;
  }

  echo json_encode($results);
}


//-----------------------------------------------------------------------
function process_route_entry($nsc, $entry) {
  ini_set('max_execution_time', 30000); // IMPORTANT: To prevent fatail error timeout

  $etap_account = $nsc->call("getAccountById", array($entry['account_number']));

  if(!$etap_account)
    return 'Acct # ' . (string)$entry['account_number'] . ' not found.';

  remove_udf($nsc, $etap_account, $entry['udf']);
  apply_udf($nsc, $etap_account, $entry['udf']);
  
  if(checkForError($nsc))
    return 'Error: ' . $nsc->faultcode . ': ' . $nsc->faultstring;

  return $nsc->call("addGift", [[
    'accountRef' => $etap_account['ref'],
    'amount' => $entry['gift']['amount'],
    'fund' => $entry['gift']['fund'],
    'campaign' => $entry['gift']['campaign'],
    'approach' => $entry['gift']['approach'],
    'note' => $entry['gift']['note'],
    'date' => formatDateAsDateTimeString($entry['gift']['date']),
    'valuable' => [
      'type' => 5,
      'inKind' => []
    ]
  ], 
    false
  ]);
}


//-----------------------------------------------------------------------
/* $note format: {'id': account_number, 'Note': note, 'Date': date} */
/* Returns response code 200 on success, 400 on failure */
function add_note($nsc, $note) {
  $account = $nsc->call("getAccountById", array($note["id"]));
  checkForError($nsc);

  // Define Note
  $trans = array(
    'accountRef' => $account['ref'],
    'note' => $note['Note'],
    'date' => formatDateAsDateTimeString($note['Date'])
  );

  $status = $nsc->call("addNote", array($trans, false));
  
  if(is_array($status)) {
    $status = $status["faultstring"];
    http_response_code(400);
    echo 'add_note failed: ' . $status;
  }
  else {
    write_log('Note added for account ' . $note['id']);
    http_response_code(200);
    echo $status;
  }
}

//-----------------------------------------------------------------------
function update_note($nsc, $data) {
  $note = $nsc->call('getNote', array($data['ReferenceNumber']));
  $note['note'] = $data['Note'];
  $status = $nsc->call('updateNote', array($note, false));
  
  if(is_array($status)) {
    $status = $status["faultstring"];
    http_response_code(400);
    echo 'update_note failed';
  }
  else {
    write_log('Note updated for account ' . $data['id']);
    http_response_code(200);
    echo $status;
  }
}


//-----------------------------------------------------------------------
function add_accounts($db, $nsc, $submissions) {
  $num_errors = 0;
  
  for($n=0; $n<count($submissions); $n++) {
    $submission = $submissions[$n];

    // Clear empty UDF fields (i.e. Office Notes may be blank)
    foreach($submission['udf'] as $key=>$value) {
      if(empty($value))
        $submission['udf'] = remove_key($submission['udf'], $key);
    }

    // Modify existing eTap account
    if(!empty($submission['existing_account'])) {
      $status = modify_account($db, $nsc, 
        $submission['existing_account'], 
        $submission['udf'], 
        $submission['persona']
      );

      if($status != 'Success')
        $num_errors++;
      
      $result = $db->insertOne([ 
        'function' => 'add_accounts',
        'request_id' => $submission['request_id'],
        'row' => $submission['row'],
        'status' => $status
      ]);

      continue;
    }

    /******** Create new account ********/
    
    // Personas
    $account = $submission['persona'];
    $udf = $submission['udf'];

    // User Defined Fields
    // Create proper DefinedValue object
    foreach($udf as $key=>$value) {
      if($key != 'Block' && $key != 'Neighborhood') {
        $account['accountDefinedValues'][] = [
          'fieldName'=>$key,
          'value'=>$value
        ];
      }
      // Multi-value UDF like Block and Neighborhood need to each be separate array 
      // for each comma-separated value
      else {
        $list = explode(",", $value);
        for($j=0; $j<count($list); $j++) {
          $account['accountDefinedValues'][] = ['fieldName'=>$key, 'value'=>$list[$j]];
        }
      }
    }

    $status = $nsc->call("addAccount", array($account, false));
    
    if(is_array($status)) {
      $status = $status['faultstring'];
      error_log('Add account error: ' . $status);
      $num_errors++;
    }
    else
      write_log('Added account ' . $account['name']);

    $result = $db->insertOne([ 
      'function' => 'add_accounts',
      'request_id' => $submission['request_id'],
      'row' => $submission['row'],
      'status' => $status
    ]);

  }

  write_log((string)count($submissions) . ' accounts added/updated. ' . (string)$num_errors . ' errors.');
}

// $udf is associative array ie. ["Status"=>"Active", ...], not DefinedValue object.
// the call to apply_udf() converts to DefinedValue format
// $persona is associative array
//-----------------------------------------------------------------------
function modify_account($db, $nsc, $id, $udf, $persona) {
  
  $account = $nsc->call("getAccountById", [$id]);

  if(!$account)
    return write_log('modify_account(): Id ' . (string)$id . ' does not exist');

  foreach($persona as $key=>$value) {
    $account[$key] = $value;
  }

  // Fix blank firstName / lastName bug in non-business accounts
  if($account['nameFormat'] != 3)  {
    if(!$account['lastName'] || !$account['firstName']) {
      $split = explode(' ', $account['name']);
      $account['firstName'] = $split[0];
      $account['lastName'] = $split[count($split)-1];
    }
  }

  $ref = $nsc->call("updateAccount", [$account, false]);

  if(checkForError($nsc))
    return write_log('in modify_account(): eTap API updateAccount() error: ' . $nsc->faultcode . ': ' . $nsc->faultstring);

  // Now update UDF fields 
  remove_udf($nsc, $account, $udf);
  apply_udf($nsc, $account, $udf);
  
  if(checkForError($nsc))
    return write_log('in modify_account(): Error ' . $nsc->faultcode . ': ' . $nsc->faultstring);

  write_log('Updated account ' . $account['firstName'] . ' ' . $account['lastName'] . ' (' . $account['id'] . ')');

  return 'Success';
}


//-----------------------------------------------------------------------
function no_pickup($nsc, $account_id, $date, $next_pickup) {
  $account = $nsc->call("getAccountById", array($account_id));
  $office_notes = "";
  $udf = $account['accountDefinedValues'];

  foreach($udf as $key=>$value) {
    if(in_array("Office Notes", $value, true))
      $office_notes = $value['value'];
  }

  $no_pickup_note = $office_notes . ' No Pickup ' . $date;
  echo 'No Pickup request received! Thanks';

  // params: db_ref, defined_values, create_field_and_values (bool)
  $status = $nsc->call("applyDefinedValues", [
    $account['ref'],
    array(
      ['fieldName'=>'Office Notes', 'value'=>$no_pickup_note],
      ['fieldName'=>'Next Pickup Date', 'value'=>$next_pickup]
    ),
    false
  ]);

  // params: Note Obj, createFieldAndValues (bool)
  $status = $nsc->call("addNote", [[
    'accountRef' => $account['ref'],
    'note' => 'No Pickup',
    'date' => formatDateAsDateTimeString($date)
    ],
    false
  ]);
  
  write_log('Account ' . $account_id . ' No Pickup');
}

//-----------------------------------------------------------------------
//Clear all the User Defined Field values
//$udf: array of defined field names
//$account: eTap account
function remove_udf($nsc, $account, $udf) {
  $udf_remove = [];

  // Cycle through numbered array of all UDF values. Defined Fields with
  // multiple values like checkboxes will contain an array element for each value
  foreach($account['accountDefinedValues'] as $key=> $field) {
    if(array_key_exists($field['fieldName'], $udf))
      $udf_remove[] = $account["accountDefinedValues"][$key];       
  }

  if(empty($udf_remove))
    return false;

  $nsc->call('removeDefinedValues', array($account["ref"], $udf_remove, false));

  if(checkForError($nsc))
    return 'remove_udf error: ' . $nsc->faultcode . ': ' . $nsc->faultstring;
}

//-----------------------------------------------------------------------
// Converts associative array of defined values into DefinedValue eTap 
// object, modifies account
// $udf: associative array of udf_names=>values
// $account: eTap Account object
function apply_udf($nsc, $account, $udf) {
  $definedvalues = [];
  
  foreach($udf as $fieldname=>$fieldvalue) {
    if(!$fieldvalue)
      continue;
    else if(($fieldname == 'Block' || $fieldname == 'Neighborhood') && 
            strpos($fieldvalue, ',') !== FALSE) {
        
      // Multi-value UDF's (Neighborhood, Block) need array for each value 
      $split = explode(',', $fieldvalue);
      
      foreach($split as $e) {
        $definedvalues[] = [
          'fieldName' => $fieldname,
          'value' => $e
        ];
      }
    }
    else {
      $definedvalues[] = [
        'fieldName' => $fieldname,
        'value' => (string)$fieldvalue
      ];
    }
  }

  if(empty($definedvalues))
    return false;

  $nsc->call('applyDefinedValues', array($account["ref"], $definedvalues, false));
  
  if(checkForError($nsc))
    return 'apply_udf error: ' . $nsc->faultcode . ': ' . $nsc->faultstring;
}

//-----------------------------------------------------------------------
function check_duplicates($nsc, $persona_fields) {
  $search = array(
    'accountRoleTypes' => 1,
    'allowEmailOnlyMatch' => false,
  );

  $response = $nsc->call("getDuplicateAccounts", array($persona_fields));
  
  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    error_log('getDuplicateAccounts error');
    return false;
  }

  if(!empty($response)) {
    $duplicates = '';

    for($i=0; $i<sizeof($response); $i++) {
      $account = $response[0]['id'];
      
      if($i == 0)
        $duplicates = (string)$account;
      else
        $duplicates .= ',' . (string)$account;
    }

    write_log($duplicates);
    echo $duplicates;
  }
}

//-----------------------------------------------------------------------
function make_booking($nsc, $account_num, $udf) {
  $account = $nsc->call("getAccountById", array($account_num));
  
  if(!$account)
    return false;

  $act_office_notes = '';

  // Find existing Driver and Office notes and merge them with parameter values
  foreach($account['accountDefinedValues'] as $index=>$a_udf) {
    if($a_udf['fieldName'] == 'Office Notes')
      $act_office_notes = $a_udf['value'];
    else if($a_udf['fieldName'] == 'Driver Notes')
      $udf['Driver Notes'] = $a_udf['value'] . '\n' . $udf['Driver Notes'];
    // If we're booking onto a natural block, just a later one, we don't want
    // to include a ***RMV BLK*** directive
    else if($a_udf['fieldName'] == 'Block' && $a_udf['value'] == $udf['Block']) {
      $udf['Office Notes'] = '';
    }
  }

  $udf['Office Notes'] = $act_office_notes;

  apply_udf($nsc, $account, $udf);

  if(checkForError($nsc)) {
    http_response_code(400);  
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    return;
  }

  http_response_code(200);  
  write_log('Booked Account #' . $account_num . ' on Block ' . $udf['Block']);
  echo 'Booked successfully!';
}

//-----------------------------------------------------------------------
function build_viamente_route($nsc, $api_url, $api_key, $query_category, $query, $date) {
  require('viamente.php');
  
  $request = [
    'start' => 0,
    'count' => 500,
    'query' => "$query_category::$query"
  ];

  $response = $nsc->call("getExistingQueryResults", array($request));

  write_log($response['count'] . ' accounts in query ' . $query . ', category: ' . $query_category);

  if(checkForError($nsc)) {
    echo 'Error code ' . $nsc->faultcode . ': ' . $nsc->faultstring;
    exit;
  }
  
  $route = [
    'name' => $query,
    'orders' => []
  ];

  foreach($response['data'] as $account) {
    $order = [
      'name' => $account['name'],
      'location' => [
        'address' => $account['address'] . ', ' . $account['city'] . ', ' . $account['postalCode']
      ],
      'serviceTimeMin' => 3,
      'customFields' => [
        'id' => $account['id'],
        'phoneNumber' => $account['phones'][0]['number'],
        'block' => [],
        'neighborhood' => []
      ]
    ];
  
    // Get Block, Neighborhood, Next Pickup Date, Status
    foreach($account['accountDefinedValues'] as $udf) {
      if($udf['fieldName'] == 'Next Pickup Date')
        $order['customFields']['nextPickupDate'] = $udf['value'];
      else if($udf['fieldName'] == 'Neighborhood')
        $order['customFields']['neighborhood'][] = $udf['value'];
      else if($udf['fieldName'] == 'Block')
        $order['customFields']['block'][] = $udf['value'];
      else if($udf['fieldName'] == 'Status')
        $order['customFields']['status'] = $udf['value'];
      else if($udf['fieldName'] == 'Driver Notes')
        $order['customFields']['driverNotes'] = $udf['value'];
      else if($udf['fieldName'] == 'Office Notes')
        $order['customFields']['officeNotes'] = $udf['value'];
      else if($udf['fieldName'] == 'GPS')
        $order['customFields']['GPS'] = $udf['value'];
    }

    if(!empty($order['customFields']['neighborhood']))
      $order['customFields']['neighborhood'] = implode(', ', $order['customFields']['neighborhood']);
    $order['customFields']['block'] = implode(', ', $order['customFields']['block']);

    $route['orders'][] = $order;
  }

  $subfleetsRes = executeRest($api_url."/subfleets", 'GET', $api_key);
  $subfleets = json_decode($subfleetsRes, true);
  $subfleetID = $subfleets['subfleets'][0]['id'];
  $create_new_routeplan_request['subfleetID'] = $subfleetID;

  echo "<h1>Create new routeplan</h1>\n";
  $routeplanRes = executeRest($api_url."/routeplans", 'POST', $api_key, json_encode_ex($route));

  $routeplanResArr = json_decode($routeplanRes, true);

  echo "<h1>Get details about newly created routeplan</h1>\n";
  executeRest($api_url."/routeplans/".$routeplanResArr['id'], 'GET', $api_key);

  http_response_code(200);
}

//-----------------------------------------------------------------------
/* returns date value from eTapestry API */
function get_next_pickup($nsc, $email) {
  $dv = [
    'email' => $email,
    'accountRoleTypes' => 1,
    'allowEmailOnlyMatch' => true
  ]; 

  $response = $nsc->call("getDuplicateAccount", array($dv));

  if(empty($response))
    echo "The email " . $email . " was not found.";
  else {
    // Loop through array and extract fieldName = "Next Pickup Date"
    foreach($response as $search) {
      if(!is_array($search))
        continue;

      foreach($search as $searchArray) {
        extract($searchArray);
        if($fieldName == 'Next Pickup Date') {
          write_log('Next Pickup for ' . $email . ': ' . formatDateAsDateTimeString($value));
          $DoP = formatDateAsDateTimeString($value);
          echo $DoP;
          return true;
        }
      }
    }
  }
}

/********* Misc Helper Functions ************/

function default_value($var, $default) {
  return empty($var) ? $default : $var;
}

function add_if_key_exists($dest, $key, $arr) {
  if(array_key_exists($key, $arr))
    $dest[$key] = $arr[$key];
}

function remove_key($array,$key){
    $holding=array();
    foreach($array as $k => $v){
        if($key!=$k){
            $holding[$k]=$v;
        }
    }    
    return $holding;
}


?>