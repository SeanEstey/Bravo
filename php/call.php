<?php
	/* On success, returns {'status':'SUCCESS', 'result':'<data>'}
	 * On fail, returns {'status':'FAILED', 'description':'<str>', 'result':'<optional>'}
	 */

	require('util.php');
	require('etap.php');
	require('main.php');
	ini_set('log_errors', 1);
	ini_set('error_log', $ERROR_LOG);

    $t1 = start_timer();
	$agcy = $argv[1];
	$username = $argv[2];
	$password = $argv[3];
    $wsdl_url = $argv[4];
	$func = $argv[5];
	$sandbox = $argv[6] === 'true'? true: false;
	$data = json_decode($argv[7], true);

	$nsc = get_endpoint($username, $password, $wsdl_url);
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
			case 'get_acct_by_ref':
				$rv = get_acct($id=NULL, $ref=$data['ref']);
				break;
			case 'get_accts_by_ref':
				$rv = get_accts($acct_ids=NULL, $acct_refs=$data['acct_refs']);
				break;
			case 'get_accts':
				$rv = get_accts($acct_ids=$data['acct_ids'], $acct_refs=NULL);
				break;
			case 'find_acct_by_phone':
				$rv = find_acct_by_phone($data['phone']);
				break;
			case 'get_gift_histories':
				$rv = gift_histories($data['acct_refs'], $data['start'], $data['end']);
				break;
            case 'donor_history':
                $rv = journal_entries($data['acct_ref'], $data['start'], $data['end'], [1,5]);
                break;
            case 'get_gifts':
                $rv = journal_entries($data['ref'], $data['startDate'], $data['endDate'], [5]);
                break;
			case 'get_upload_status':
				$rv = get_upload_status($data['request_id'], $data['from_row']);
				break;
			case 'get_query':
				$rv = get_query($data['query'], $data['category'], arr_get($data, 'start', null), arr_get($data, 'count', null));
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
				$rv = add_accts($data['accts']);
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
            case 'get_next_pickup':
                $rv = get_next_pickup($data['email']);
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
		$msg = 'status=EXCEPTION, func="' . $func . '"';
		//err_log($msg);
		debug_log($msg . ', desc="' . $e->getMessage() . '"');

		echo json_encode([
			'status'=>'FAILED',
			'description'=>$e->getMessage()]);

		$nsc->call("logout");
		exit;
	}

	if(is_error($nsc)) {
		$msg = 'status=FAILED, func="' . $func . '"';
		$err = get_error($nsc, $log=false);

		debug_log($msg . ', desc="' . $err . '", rv="' . json_encode($rv) . '"');

		echo json_encode([
			'status'=>'FAILED',
			'description'=>$err,
			'result'=>$rv]);

		$nsc->call("logout");
		exit;
	}
	else {
		debug_log('status=SUCCESS, func="' . $func . '" [' . end_timer($t1) . 's]');

		echo json_encode([
		  'status'=>'SUCCESS',
		  'result'=>$rv]);

		$nsc->call("logout");
		exit;
	}
?>
