<?php
	require('utils.php');
	require('etap.php');
  require('bravo.php');
  ini_set('log_errors', 1);
  ini_set('error_log', $ERROR_LOG);

	$sandbox = false;
	$agcy = $func = $data = $etap_conf = null;
	get_inputs(); // Define $agcy, $func, $data, $etap_conf with json/form data 
	$nsc = get_endpoint($etap_conf);
	$rv = NULL;

	try {
		switch($func) {
			case 'get_block_size':
					$rv = get_block_size($data['category'], $data['query']);
					break;
			case 'get_route_size':
					$rv = get_route_size($data['category'], $data['query'], $data['date']);
					break;
			case 'get_next_pickup':
					$rv = get_next_pickup($data['email']);
					break;
			case 'get_acct':
					$rv = get_acct($id=$data['acct_id']);
					break;
			case 'get_accts_by_ref':
					$rv = get_accts($acct_refs=$data['acct_refs']);
					break;
			case 'get_accts':
					$rv = get_accts($acct_ids=$data['acct_ids']);
					break;
			case 'find_acct_by_phone':
					$rv = find_acct_by_phone($data['phone']);
					break;
			case 'get_gift_histories':
					$rv = gift_histories($data['acct_refs'], $data['start'], $data['end']);
					break;
			case 'get_upload_status':
					$rv = get_upload_status($data['request_id'], $data['from_row']);
					break;
			case 'get_query':
					$rv = get_query($data['query'], $data['category']);
					break;
			case 'get_num_active_processes':
					$rv = num_php_fpms();
					break;
			case 'check_duplicates':
					$rv = check_duplicates($data);
					break;
			case 'modify_acct':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = modify_acct($data['acct_id'], $data['udf'], $data['persona']);
					break;
			case 'add_accts':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = add_accts($data);
					break;
			case 'add_note':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = add_note($data['acct_id'], $data['date'], $data['body']);
					break;
			case 'update_note':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = update_note($data['acct_id'], $data['ref'], $data['body']);
					break;
			case 'process_entries':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = process_entries($data['entries']);
					break;
			case 'skip_pickup':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = skip_pickup($data['acct_id'], $data['date'], $data['next_pickup']);
					break;
			case 'make_booking':
					if($sandbox) {$rv = sandbox_err($func); break;}
					$rv = make_booking($data['acct_id'], $data['udf'], $data['type']);
					break;
			default:
					throw new Exception('invalid function=' . $func);
					break;
		}
	} 
	catch(Exception $e) {
			debug_log('Error in view="' . $func . '". ' . (string)$e);
			debug_log(print_r($data, true));
			http_response_code(500);
			echo json_encode($e->getMessage());
			$nsc->call("logout");
			exit;
	}

	if(http_response_code() != 200) {
			debug_log('response_code=' . http_response_code() . ' message=' . $rv);
			echo json_encode($rv);
			$nsc->call("logout");
			exit;
	}

	echo json_encode($rv);
	$nsc->call("logout");
	debug_log('status=SUCCESS, func="' . $func . '", code=' . http_response_code());
	exit;
?>
