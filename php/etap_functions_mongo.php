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

  if(empty($account)) {
    echo 'No matching accounts for ' . $account_number;
    return false;
  }

  echo json_encode($account);
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
/* 
  Update UDF's for accounts from Gift Entries spreadsheet 
   $account format: {
    'account_num': int,
    'request_id': int,
    'row': int,
    'udf': {
      'field_name': field_value,
      'field_name': field_value
    }
  }
*/
function update_udf($db, $nsc, $accounts) {
  ini_set('max_execution_time', 3000); // IMPORTANT: To prevent fatail error timeout
  $num_errors = 0;
  
  // For each account, clear UDF's then replace them 
  for($i=0; $i<count($accounts); $i++) {
    $etap_account = $nsc->call("getAccountById", array($accounts[$i]["account_num"]));
    
    $status = 'OK';
    
    if(checkForError($nsc)) {
      $status = 'Account ' . (string)$accounts[$i]['account_num'] . ' not found. Was it merged? ';
      $status += $nsc->faultcode . ': ' . $nsc->faultstring;
      $num_errors++;
    }
    else {
      remove_udf($nsc, $etap_account, $accounts[$i]['udf']);
      apply_udf($nsc, $etap_account, $accounts[$i]['udf']);

      if(checkForError($nsc)) {
        $status = 'Update account error: ' . $nsc->faultcode . ': ' . $nsc->faultstring;
        $num_errors++;
      }
    }

    $result = $db->insertOne([ 
      'function' => 'update_udf',
      'request_id' => $accounts[$i]['request_id'],
      'row' => $accounts[$i]['row'],
      'status' => $status
    ]);
  }

  write_log((string)count($accounts). " accounts updated. $num_errors errors.");
}



//-----------------------------------------------------------------------
function update_persona($account_num, $persona) {
  $account = $nsc->call("getAccountById", array($account_num));

  if(isset($persona['email']))
    $account['email'] = $persona['email'];

  if(isset($persona['voice'])) {
    foreach($account['phones'] as $idx=>$phone) {
      if($phone['type'] == 'Voice')
        $account['phones'][$idx]['number'] = $persona['voice'];
    }
  }

  if(isset($persona['mobile'])) {
    foreach($account['phones'] as $idx=>$phone) {
      if($phone['type'] == 'Mobile')
        $account['phones'][$idx]['number'] = $persona['mobile'];
    }
  }

  $nsc->call('updateAccount', [$account, false]);

  if($nsc->fault || $nsc->getError())
    if(!$nsc->fault)
      error_log("Error: " . $nsc->getError());

  error_log('Updated persona for Account ' . (string)$account_num . ': ' . $_POST['persona']);

  return true;
}


//-----------------------------------------------------------------------
/* $note format: {'Account': account_num, 'Note': note, 'Date': date} */
/* Returns response code 200 on success, 400 on failure */
function add_note($nsc, $note) {
  $account = $nsc->call("getAccountById", array($note["Account"]));
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
    write_log('Note added for account ' . $note['Account']);
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
    write_log('Note updated for account ' . $data['Account']);
    http_response_code(200);
    echo $status;
  }
}

//-----------------------------------------------------------------------
/* Add Journal Gifts for accounts in Gift Entries spreadsheet */
function add_gifts($db, $nsc, $gifts, $fund, $campaign, $approach) {
  ini_set('max_execution_time', 3000); // IMPORTANT: To prevent fatail error timeout
  $num_errors = 0;

  for($i=0; $i<count($gifts); $i++) {
    $gift = $gifts[$i];
    $account = $nsc->call("getAccountById", [$gift['account_num']]);
    checkForError($nsc);

    $etap_gift = [
      'accountRef' => $account['ref'],
      'amount' => $gift['gift'],
      'fund' => $fund,
      'campaign' => $campaign,
      'approach' => $approach,
      'note' => $gift['note'],
      'date' => formatDateAsDateTimeString($gift['date'])
    ];

    $status = $nsc->call("addGift", array($etap_gift, false));
   
    if(checkForError($nsc)) {
      $status = $nsc->faultcode . ': ' . $nsc->faultstring;
      $num_errors++;
    }
    
    $result = $db->insertOne([ 
      'function' => 'add_gifts',
      'request_id' => $gift['request_id'],
      'row' => $gift['row'],
      'status' => $status
    ]);
  }

  write_log((string)count($gifts) . ' gifts added. ' . (string)$num_errors . ' errors.');
}

//-----------------------------------------------------------------------
function add_accounts($db, $nsc, $submissions) {
  $num_errors = 0;
  
  for($n=0; $n<count($submissions); $n++) {
    $submission = $submissions[$n];

    if(!empty($submission['existing_account'])) {
      add_to_existing_account($db, $nsc, $submission, $submission['existing_account']);
      continue;
    }

    $persona = $submission['persona_fields'];
    $account = [
      'nameFormat' => 1,
      'personaType' => $persona['Persona Type'],
      'name' => $persona['First Name'] . " " . $persona['Last Name'],
      'sortName' => $persona['Last Name'] . ", " . $persona['First Name'],
      'firstName' => $persona['First Name'],
      'lastName' => $persona['Last Name'],
      'shortSalutation' => $persona['First Name'],
      'longSalutation' => $persona['Title'] . " " . $persona['Last Name'],
      'envelopeSalutation' => $persona['Title'] . ' ' . $persona['First Name'] . ' ' . $persona['Last Name'],
      'address' => $persona['Address'],
      'city' => $persona['City'],
      'state' => 'AB',
      'country' => 'CA',
      'postalCode' => $persona['Postal'],
      'email' => $persona['Email']
    ];

    // Optional Persona Fields

    if(!empty($persona['Phone'])) {
      $account['phones'][] = [
        'type' => 'Voice',
        'number' => $persona['Phone']
      ];
      
      if(!empty($persona['Mobile'])) {
        $account['phones'][] = [
          'type' => 'Mobile',
          'number' => $persona['Mobile']
        ];
      }
    }

    $udf = $submission['defined_fields'];

    $account["accountDefinedValues"] = [
      ['fieldName'=>'Status', 'value'=>$udf['Status']],
      ['fieldName'=>'Signup Date', 'value'=>$udf['Signup Date']],
      ['fieldName'=>'Dropoff Date', 'value'=>$udf['Dropoff Date']],
      ['fieldName'=>'Next Pickup Date', 'value'=>$udf['Next Pickup Date']],
      ['fieldName'=>'Tax Receipt', 'value'=>$udf['Tax Receipt']],
      ['fieldName'=>'Reason Joined', 'value'=>$udf['Reason Joined']]
    ];
    
    $blocks = explode(",", $udf['Block']);
    for($j=0; $j<count($blocks); $j++) {
      $account['accountDefinedValues'][] = ['fieldName'=>'Block', 'value'=>$blocks[$j]];
    }

    // Optional User Defined Fields

    if(!empty($udf['Office Notes']))
      $account['accountDefinedValues'][] = ['fieldName' => 'Office Notes', 'value'=>$udf['Office Notes']];

    if(!empty($udf['Driver Notes']))
      $account['accountDefinedValues'][] = ['fieldName' => 'Driver Notes', 'value'=>$udf['Driver Notes']];

    if(!empty($udf['Referrer']))
      $account['accountDefinedValues'][] = ['fieldName'=>'Referrer', 'value'=>$udf['Referrer']];
      
    if(array_key_exists('Neighborhood', $udf)) {
      $neighborhoods = explode(",", $udf['Neighborhood']);
      for($j=0; $j<count($neighborhoods); $j++) {
        $account['accountDefinedValues'][] = ['fieldName'=>'Neighborhood', 'value'=>$neighborhoods[$j]];
      }
    }

    $status = $nsc->call("addAccount", array($account, false));
    
    if(is_array($status)) {
      $status = $status['faultstring'];
      error_log('Add account error: ' . $status);
      $num_errors++;
    }

    $result = $db->insertOne([ 
      'function' => 'add_accounts',
      'request_id' => $submission['request_id'],
      'row' => $submission['row'],
      'status' => $status
    ]);
  }
  
  write_log((string)count($submissions) . ' accounts added. ' . (string)$num_errors . ' errors.');
}


//-----------------------------------------------------------------------
function add_to_existing_account($db, $nsc, $account, $account_number) {
  $to_update = [
    'request_id' => $account['request_id'],
    'row' => $account['row'],
    'account_num' => $account_number,
    'udf' => $account['defined_fields']
  ];

  // Add Defined Fields
  update_udf($db, $nsc, [$to_update]);

  write_log("Updated account $account_number Defined Fields");

  // Get old account
  $etap_account = $nsc->call("getAccountById", array($account_number));

  if(empty($etap_account)) {
    return;
  }

  // See if we have updated Email, Phone, or Address info
  if(!empty($account['persona_fields']['Email'])) {
    $etap_account['email'] = $account['persona_fields']['Email'];
  }

  if(!empty($account['persona_fields']['Mobile']))
    $etap_account['phones'][] = [
      'type' => 'Mobile',
      'number' => $account['persona_fields']['Mobile']
    ];

  $response = $nsc->call("updateAccount", [$etap_account, false]);

  checkForError($nsc);
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

  $nsc->call('removeDefinedValues', array($account["ref"], $udf_remove, false));

  if(checkForError($nsc))
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
}

//-----------------------------------------------------------------------
// $udf: array of udf_names=>values
// $account: etap account
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

  $nsc->call('applyDefinedValues', array($account["ref"], $definedvalues, false));
  
  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    return $nsc->faultcode . ': ' . $nsc->faultstring;
  }
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
  
  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    http_response_code(400);
    return;
  }

  // Append Driver and Office Notes to existing notes
  foreach($account['accountDefinedValues'] as $index=>$a_udf) {
    if($a_udf['fieldName'] == 'Office Notes')
      $udf['Office Notes'] = $a_udf['value'] . '\n' . $udf['Office Notes'];
    else if($a_udf['fieldName'] == 'Driver Notes')
      $udf['Driver Notes'] = $a_udf['value'] . '\n' . $udf['Driver Notes'];
  }

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


?>
