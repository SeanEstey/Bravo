<?php
  ini_set('log_errors', 1);
  ini_set('error_log', '/var/www/empties/etap/log');
  
  function write_log($msg) {
    global $association;
    $line = '[' . date('j-M-Y g:iA') . ' ' . strtoupper($association) . ']: ' . $msg . "\n\r";
    file_put_contents('log', $line, FILE_APPEND);
  }

  require('etap_functions_mongo.php');
  require 'vendor/autoload.php';

  if(!isset($_POST['data'])) {
    $association = 'wsf';
    $arr = json_decode(file_get_contents("php://input"));
    $arr = get_object_vars($arr);

    $func = $arr['func'];
    $data = get_object_vars($arr['data']);
    $keys = get_object_vars($arr['keys']);
  }
  else {
    $func = $_POST['func'];
    $data = json_decode($_POST['data'], true);
    $keys = json_decode($_POST['keys'], true);
  }

  $association = $keys['association_name'];
  
  $m = new MongoDB\Driver\Manager('mongodb://localhost:27017');
  $db = new MongoDB\Collection($m, "$association.jobs");

  $nsc = new nusoap_client($keys['etap_endpoint'], true);

  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    exit;
  }

  $newEndpoint = $nsc->call('login', array($keys['etap_user'], $keys['etap_pass']));

  if(checkForError($nsc)) {
    echo $nsc->faultcode . ': ' . $nsc->faultstring;
    exit;
  }

  if($newEndpoint != "") {
    $nsc = new nusoap_client($newEndpoint, true);
    checkForError($nsc);
    $nsc->call("login", array($keys['etap_user'], $keys['etap_pass']));
    checkForError($nsc);
  }

  /* Call appropriate function */

  switch($func) {
    case 'get_num_active_processes':
      $res = [];
      exec("/etc/init.d/php7.0-fpm status | grep 'Processes active'", $res);
      $start_index = strpos($res[0], 'Processes active:') + 17;
      $end_index = strpos($res[0], ',');
      $num_processes = substr($res[0], $start_index, $end_index-$start_index); 
      echo $num_processes;
      break;

    case 'process_gifts':
      break;

    case 'add_gifts':
      add_gifts(
        $db, 
        $nsc, 
        $data['gifts'], 
        $data['etap_gift_fund'],
        $data['etap_gift_campaign'], 
        $data['etap_gift_approach']
      );
      break;

    case 'add_accounts':
      add_accounts($db, $nsc, $data);
      break;
    
    case 'add_note':
      add_note($nsc, $data);
      break;
    
    case 'update_note':
      update_note($nsc, $data);
      break;
      
    case 'update_udf':
      update_udf($db, $nsc, $data);
      break;

    case 'get_account':
      get_account($nsc, $data['account_num']);
      break;
    
    case 'get_upload_status':
      $request_id = intval($data['request_id']);
      if(!empty($data['from_row']))
        $from_row = $data['from_row'];
      else
        $from_row = 2;
      
      get_upload_status($db, $request_id, $from_row);
      break;
      
    case 'get_block_size':
      get_block_size($nsc, $data['query_category'], $data['query']);
      break;

    case 'get_scheduled_run_size':
      get_scheduled_run_size($nsc, $data['query_category'], $data['query'], $data['date']);
      break;

    case 'get_next_pickup':
      get_next_pickup($nsc, $data['email']);
      break;
    
    case 'check_duplicates':
      check_duplicates($nsc, $data);
      break;
    
    case 'no_pickup':
      no_pickup($nsc, $data['account'], $data['date'], $data['next_pickup']);
      break;

    case 'make_booking':
      make_booking($nsc, $data['account_num'], $data['udf']);
      break;

    case 'build_viamente_route':
      build_viamente_route(
        $nsc,
        $keys['viamente_api_url'], 
        $keys['viamente_api_key'],
        $data['query_category'],
        $data['query'],
        $data['date']
      );
      break;

    default:
      error_log("Invalid function '" . $func . "'");
      echo 'Invalid Function';
      http_response_code(500);
      break;

    checkStatus($nsc);
    $nsc->call("logout");
    exit;
  }
?>
