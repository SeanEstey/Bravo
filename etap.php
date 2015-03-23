<?php

require("./lib/nusoap.php");

ini_set('log_errors', 1);
ini_set('error_log', '/data/wsf/error.log');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $func = $_POST["func"];
  $data = json_decode($_POST["data"]);
}
else if ($_SERVER['REQUEST_METHOD'] === 'GET') {
  $func = $_GET["func"];
}
else {
  error_log('Not GET or POST');
  echo 'Fail';
  exit;
}

// GLOBALS
$nsc = startEtapSession();
$m = new MongoClient();
$db = $m->wsf;
$collection = $db->giftentries;

switch($func) {
  case 'no_pickup':
    $account_id = $_GET['account'];
    $date = $_GET['date'];
    $next_pickup = $_GET['next_pickup'];
    no_pickup($account_id, $date, $next_pickup);
    http_response_code(200);
  
  case 'add_notes':
    //add_notes($data);
    break;
  
  case 'add_gifts':
    $gifts = json_decode($_POST["data"]);
    add_gifts($gifts);
    http_response_code(200);
    break;
  
  case 'update_accounts':
    $accounts = json_decode($_POST["data"]);
    update_accounts($accounts);
    http_response_code(200);
    break;
  
  case 'add_accounts':
    error_log('running add_accounts');
    $submissions = json_decode($_POST["data"]);
    add_accounts($submissions);
    http_response_code(200);  
    break;
  
  case 'get_block_size':
    $category = $_GET['category'];
    $query = $_GET['query'];
    get_block_size($category, $query);
    http_response_code(200);  
    break;
  
  case 'get_upload_status':
    $request_id = intval($_GET['request_id']);
    $from_row = intval($_GET['from_row']);
    get_upload_status($request_id, $from_row);
    http_response_code(200);
    break;

  default:
    error_log('Invalid function');
    echo 'Invalid Function';
    http_response_code(500);
    break;

  checkStatus($nsc);
  $nsc->call("logout");
  exit;
}

function startEtapSession() {
  $loginId = "wsf_api";
  $password = "snookie";
  $endpoint = "https://sna.etapestry.com/v2messaging/service?WSDL";

  $nsc = new nusoap_client($endpoint, true);
  checkStatus($nsc);
  $newEndpoint = $nsc->call("login", array($loginId, $password));
  checkStatus($nsc);

  if ($newEndpoint != "") {
    $nsc = new nusoap_client($newEndpoint, true);
    checkStatus($nsc);
    $nsc->call("login", array($loginId, $password));
    checkStatus($nsc);
  }

  return $nsc;
}

function checkStatus($nsc) {
  if ($nsc->fault || $nsc->getError()) {
    if (!$nsc->fault) {
      error_log("Error: " . $nsc->getError());
    }
    else {
      error_log("Fault Code: " . $nsc->faultcode);
      error_log("Fault String: " .$nsc->faultstring);;
    }
    exit;
  }
}

function formatDateAsDateTimeString($dateStr) {
  if ($dateStr == null || $dateStr == "") return "";
  if (substr_count($dateStr, "/") != 2) return "[Invalid Date: $dateStr]";

  $separator1 = stripos($dateStr, "/");
  $separator2 = stripos($dateStr, "/", $separator1 + 1);

  $day = substr($dateStr, 0, $separator1);
  $month = substr($dateStr, $separator1 + 1, $separator2 - $separator1 - 1);
  $year = substr($dateStr, $separator2 + 1);

  
  return ($day > 0 && $month > 0 && $year > 0) ? date(DATE_ATOM, mktime(0, 0, 0, $month, $day, $year)) : "[Invalid Date: $dateStr]";
}

function no_pickup($account_id, $date, $next_pickup) {
  global $nsc;
  $account = $nsc->call("getAccountById", array($account_id));
  $office_notes = "";
  $udf = $account['accountDefinedValues'];

  foreach($udf as $key=>$value) {
    if(in_array("Office Notes", $value, true))
      $office_notes = $value['value'];
  }

  $no_pickup_note = $office_notes . ' No Pickup ' . $date;
  echo 'No Pickup request received! Thanks';

  $definedvalues[] = array('fieldName'=>'Office Notes', 'value'=>$no_pickup_note);
  $definedvalues[] = array('fieldName'=>'Next P/U Date', 'value'=>$next_pickup);

  $status = $nsc->call("applyDefinedValues", array($account["ref"], $definedvalues, false));
  if(!empty($status))
    error_log('Account ' . $account_id . ' No Pickup status: ' . print_r($status,true));
      
  // Define Note
  $trans = array();
  $trans["accountRef"] = $account["ref"];
  $trans["note"] = 'No Pickup';
  $trans["noteType"] = "ETW: No Pickup";
  $trans["date"] = formatDateAsDateTimeString($date);

  $status = $nsc->call("addNote", array($trans, false));
  error_log('Account ' . $account_id . ' No Pickup status: ' . print_r($status,true));
}

function add_gifts($gifts) {
  global $nsc;
  $data = array();

  for($i=0; $i<count($gifts); $i++) {
    $gift = get_object_vars($gifts[$i]);
    $account = $nsc->call("getAccountById", array($gift["Account"]));
    checkStatus($nsc);

    // Define Gift
    $trans = array();
    $trans["accountRef"] = $account["ref"]; 
    $trans["fund"] = "WSF";
    $trans["amount"] = $gift["Gift"];
    $trans["campaign"] = "Empties to WINN";
    $trans["approach"] = "Bottle Donation";
    $trans["note"] = $gift["Note"];
    $trans["date"] = formatDateAsDateTimeString($gift["Date"]);

    $status = $nsc->call("addGift", array($trans, false));
    
    $document = array(
      "request_id" => $gift["RequestID"], 
      "row" => $gift["Row"],
    );
    
    if(is_array($status))
      $document["status"] = $status["faultstring"];
    else
      $document["status"] = $status;

    $collection->insert($document);
    error_log('Add Gift status: ' . print_r($status,true));
  }
}

function add_accounts($submissions) {
  global $nsc, $collection;
  
  for($n=0; $n<count($submissions); $n++) {
    $submission = get_object_vars($submissions[$n]);
    $account = array();
    $account["name"] = $submission["FirstName"] . " " . $submission["LastName"];
    $account["sortName"] = $submission["LastName"] . ", " . $submission["FirstName"];
    $account["personaType"] = $submission["Persona"];
    $account["address"] = $submission["Address"];
    $account["city"] = $submission["City"];
    $account["state"] = "AB";
    $account["postalCode"] = $submission["Postal"];
    
    if(empty($submission["Email"]))
        $account["email"] = "";
    else
        $account["email"] = $submission["Email"];
    
    if(empty($submission["Title"])) {
      $account["longSalutation"] = $account["name"];
      $account["envelopeSalutation"] = $account["name"];
    }
    else {
      $account["longSalutation"] = $submission["Title"] . " " . $account["name"];
      $account["envelopeSalutation"] = $account["longSalutation"];
    }

    $account["shortSalutation"] = $submission["FirstName"];

    if(!empty($submission["Phone"])) {
      $phone = array();
      $phone["type"] = "Voice";
      $phone["number"] = $submission["Phone"];
      $account["phones"] = array($phone);
    }

    $udf_names = array(
      "Status", 
      "Dropoff Date",
      "Next P/U Date", 
      "Signup Date", 
      "Neighborhood", 
      "Block",
      "Driver Notes",
      "Office Notes",
      "Account Type",
      "Reason Joined",
      "Reason Joined Note",
      "Tax Receipt");

    $form_names = array(
      "Status",
      "DropoffDate",
      "NextPickupDate",
      "SignupDate",
      "Neighborhood",
      "Block",
      "DriverNotes",
      "OfficeNotes",
      "AccountType",
      "ReasonJoined",
      "ReasonJoinedNote",
      "TaxReceipt");

    $account["accountDefinedValues"] = array();

    for($i=0; $i<count($udf_names); $i++) {
      if(empty($submission[$form_names[$i]]))
        continue; 
       
      $is_multi_field = 
        strcmp($form_names[$i],"Neighborhood") == 0 || 
        strcmp($form_names[$i],"Block") == 0;

      $has_multi_value = strpos($submission[$form_names[$i]],",");

      // For multiple values in a defined field, eTapestry requires a [fieldName, value] array for each value    
      if($is_multi_field && $has_multi_value !== FALSE) { 
        $split = explode(",", $submission[$form_names[$i]]);
          for($j=0; $j<count($split); $j++) {
            $udf = array(
              "fieldName" => $udf_names[$i],
              "value" => $split[$j]);
            array_push($account["accountDefinedValues"], $udf);
          }
      }
      else {
        $udf = array(
          "fieldName" => $udf_names[$i],
          "value" => $submission[$form_names[$i]]);
        array_push($account["accountDefinedValues"], $udf);
      }
    }

    $status = $nsc->call("addAccount", array($account, false));
    
    $document = array(
      "request_id" => $submission["RequestID"], 
      "row" => $submission["Row"],
    );
    
    if(is_array($status))
      $document["status"] = $status["faultstring"];
    else
      $document["status"] = $status;

    $collection->insert($document);
    error_log('add_accounts_db result: ' . print_r($status,true));
  }
}

function update_accounts($accounts) {
  global $nsc;
  
  $udf_names = array(
    "Status" => "Status",
    "Next P/U Date" => "NextPickupDate",
    "Neighborhood" => "Neighborhood",
    "Block" => "Block",
    "Driver Notes" => "DriverNotes",
    "Office Notes" => "OfficeNotes"
  );

  // For each account, clear UDF's via removeDefinedValues, add new values via applyDefinedValues 
  for($i=0; $i<count($accounts); $i++) {
    $submission = get_object_vars($accounts[$i]);
    $account = $nsc->call("getAccountById", array($submission["Account"]));
    //checkStatus($nsc);
    remove_udf_values($nsc, $account, $submission);
    $status = apply_udf_values($nsc, $account, $submission);

    $document = array(
      "request_id" => $submission["RequestID"], 
      "row" => $submission["Row"],
    );
    
    if(is_array($status))
      $document["status"] = $status["faultstring"];
    else
      $document["status"] = "OK";

    $collection->insert($document);
    unset($submission);
    unset($account);
    unset($status);
    unset($document);
  }
}

function add_notes($notes) {
  global $nsc;

  for($i=0; $i<count($notes); $i++) {
    $note = get_object_vars($notes[$i]);
    $account = $nsc->call("getAccountById", array($note["Account"]));

    checkStatus($nsc);

    // Define Note
    $trans = array();
    $trans["accountRef"] = $account["ref"];
    $trans["note"] = $note["Comments"] . ": '" . $note["DriverInput"] . "'";
    $trans["date"] = formatDateAsDateTimeString($note["Date"]);

    $status = $nsc->call("addNote", array($trans, false));
    
    $document = array(
      "request_id" => $note["RequestID"], 
      "row" => $note["Row"],
    );
    
    if(is_array($status))
        $document["status"] = $status["faultstring"];
    else
        $document["status"] = $status;

    $collection->insert($document);
    $note['status'] = $status;
    error_log('add_notes_db.php added: ' . print_r($note,true));
  }
}

function get_upload_status($request_id, $from_row) {
  global $nsc, $collection;

  $criteria['request_id'] = $request_id;

  if($from_row)
    $criteria['row'] = array('$gte' => $from_row);

  $cursor = $collection->find($criteria);

  if($cursor->count() === 0) {
    echo 'no results';
    exit(0);
  }

  error_log('get_upload_status: ' . (string)$cursor->count() . ' results found');

  $results = array();
  foreach ($cursor as $document) {
    unset($document["_id"]);
    $results[] = $document;
  }

  echo json_encode($results);
}

function get_block_size($category, $query) {
  global $nsc;

  if($category == "res")
      $categoryName = "ETW: Residential Runs";
  else if($category == "bus")
      $categoryName = "ETW: Business Runs";

  $request = array();
  $request["start"] = 0;
  $request["count"] = 500;
  $request["query"] = "$categoryName::$query";

  $response = $nsc->call("getExistingQueryResults", array($request));
  $num_accounts = $response["count"];

  checkStatus($nsc);

  error_log("getQueryResultStats().count(): " . $num_accounts);
  echo $num_accounts;
}




function remove_udf_values($nsc, $account, $submission) {
  global $nsc;
  global $udf_names;
  $udf_remove = array();

  foreach($account["accountDefinedValues"] as $key=> $value) {
    // Remove multiple values for Blocks or Neighborhoods
    if($value['fieldName'] == 'Neighborhood' || $value['fieldName'] == 'Block')
      $udf_remove[] = $account["accountDefinedValues"][$key];
    else if(array_key_exists($value["fieldName"], $udf_names)) { 
      // Cannot apply empty UDF. Remove instead.
      if(empty($submission[$udf_names[$value["fieldName"]]]))
        $udf_remove[] = $account["accountDefinedValues"][$key];
    }
    // Remove old deprecated fields and junk added automaticallly via eTap file imports.
    else if($value["fieldName"] == "Data Source" || $value["fieldName"] == "Residential P/U Dates")
      $udf_remove[] = $account["accountDefinedValues"][$key];
  }

  try {
    $nsc->call("removeDefinedValues", array($account["ref"], $udf_remove, false));
  }
  catch (Exception $e) {
    error_log('Caught exception: ', $e->getMessage());
  }
    
  unset($udf_remove);
}

function apply_udf_values($nsc, $account, $submission) {
  global $nsc;
  global $udf_names;

  // Add new User Defined Values
  $definedvalues = array();

  foreach($udf_names as $key => $value) {
    if(empty($submission[$udf_names[$key]]))
      continue;
    if($key == "Block" || $key == "Neighborhood") {     
      // Multi-value UDF's (Neighborhood, Block)  need array for each value 
      if(strpos($submission[$udf_names[$key]],",") !== FALSE) {
        $split = explode(",", $submission[$udf_names[$key]]);
        foreach($split as $fieldvalue) {
          $udf = array(
            "fieldName" => $key,
            "value" => $fieldvalue);
          $definedvalues[] = $udf;
        }
      }
      else {
        $udf = array();
        $udf["fieldName"] = $key;
        $udf["value"] = (string)$submission[$value];
        $definedvalues[] = $udf;
      }
    }
    else {
      $udf = array();
      $udf["fieldName"] = $key;
      $udf["value"] = (string)$submission[$value];
      $definedvalues[] = $udf;
    }
  }

  try {
    return $nsc->call("applyDefinedValues", array($account["ref"], $definedvalues, false));
  }
  catch (Exception $e) {
    error_log('Caught exception: ', $e->getMessage());
  }

  unset($definedvalues);
}

?>
