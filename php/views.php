<?php
  $LOG_FILE = '/var/www/bravo/logs/log.log';

  ini_set('log_errors', 1);
  ini_set('error_log', $LOG_FILE);
  
	function write_log($msg) {
		global $LOG_FILE;
    global $association;
    $line = '[' . date('j-M-Y g:iA') . ' php ' . strtoupper($association) . ']: ' . $msg . "\n";
    file_put_contents($LOG_FILE, $line, FILE_APPEND);
    return $msg;
  }

  require('empties.php');
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
  $db = new MongoDB\Collection($m, "$association.entries");

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

    case 'add_accounts':
      add_accounts($db, $nsc, $data);
      break;
    
    case 'add_note':
      add_note($nsc, $data);
      break;
    
    case 'update_note':
      update_note($nsc, $data);
      break;

    case 'process_route_entries':
      $entries = $data['entries'];
      $num_errors = 0;

      for($i=0; $i<count($data['entries']); $i++) { 
        $status = process_route_entry($nsc, $entries[$i]);

        if(floatval($status) == 0)
          $num_errors++;

        $result = $db->insertOne([ 
          'function' => 'process_route_entry',
          'request_id' => $data['request_id'],
          'row' => $entries[$i]['row'],
          'status' => $status
        ]);
      }

      write_log('Processed ' . (string)count($data['entries']) . ' route entries. ' . (string)$num_errors . ' errors.');

      break;
      
    case 'get_account':
      $account = get_account($nsc, $data['account_number']);
      
      if(empty($account)) {
        http_response_code(400);
        echo json_encode('No matching account for ' . $data['account_number']);
      }
      else
        echo json_encode($account);

      break;

    case 'get_accounts':
      $accounts = [];
      for($i=0; $i < count($data['account_numbers']); $i++) {
        $account = get_account($nsc, $data['account_numbers'][$i]);
        
        if($account)
          $accounts[] = $account;
      }

      write_log(count($accounts) . ' accounts retrieved.');

      echo json_encode($accounts);
      break;

    case 'modify_account':
      $status = modify_account($db, $nsc, $data['id'], $data['udf'], $data['persona']);
      
      if($status != 'Success')
        http_response_code(400);
      else
        http_response_code(200);
      
      echo $status;

      break;

    case 'get_gift_histories':
      $accounts = [];
      for($i=0; $i < count($data['account_refs']); $i++) {
        $accounts[] = get_gift_history($nsc, $data['account_refs'][$i], $data['start_date'], $data['end_date']);
      }
      
      write_log(count($accounts) . ' gift histories retrieved.');

      echo json_encode($accounts);
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
      $pickup = get_next_pickup($nsc, $data['email']);

      if(!$pickup) {
        http_response_code(400);
      }
      else 
        echo $pickup;

      break;
    
    case 'check_duplicates':
      check_duplicates($nsc, $data);
      break;
    
    case 'no_pickup':
      no_pickup($nsc, $data['account'], $data['date'], $data['next_pickup']);
      break;

    case 'make_booking':
      make_booking($nsc, $data['account_num'], $data['udf'], $data['type']);
      break;

    case 'get_query_accounts':
      $query = $data['query'];
      $category = $data['query_category'];

      $response = $nsc->call("getExistingQueryResults", [[
          'start' => 0,
          'count' => 500,
          'query' => "$category::$query"
        ]]
      );

      write_log($response['count'] . ' accounts in query ' . $data['query'] . ', category: ' . $data['query_category']);
      echo json_encode($response);

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
