<?php

require("./lib/utils.php");
require("./lib/nusoap.php");

ini_set('log_errors', 1);
ini_set('error_log', '/data/wsf/error.log');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $func = json_decode($_POST["func"]);
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
    $submissions = json_decode($_POST["data"]);
    add_accounts($submissions);
    http_response_code(200);
    
    break;
  case 'get_block_size':
    //get_block_size($data);
    break;
  case 'get_query_stats':
    //get_query_stats($data);
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
    $account["shortSalutation"] = $submission["FirstName"];
    $account["longSalutation"] = $account["name"];
    $account["envelopeSalutation"] = $account["name"];

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

  stopEtapestrySession($nsc);
  http_response_code(202);
}

function add_notes($notes) {
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

function remove_udf_values($nsc, $account, $submission) {
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
