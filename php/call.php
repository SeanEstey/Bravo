<?php
	/* On success, returns {'status':'SUCCESS', 'result':'<data>'}
	 * On fail, returns {'status':'FAILED', 'description':'<str>', 'result':'<optional>'}
	 */

    $DEBUG_LOG = '/root/bravo/logs/debug.log';
    $INFO_LOG = '/root/bravo/logs/events.log';
    $ERROR_LOG = '/root/bravo/logs/events.log';
	ini_set('log_errors', 1);
	ini_set('error_log', $ERROR_LOG);

	require('util.php');
	require('etap.php');
	require('main.php');

    $t1 = start_timer();
	$agcy = $argv[1];
	$username = $argv[2];
	$password = $argv[3];
    $wsdl_path = $argv[4];
	$func = $argv[5];
	$sandbox = $argv[6] === 'true'? true: false;
    $timeout = (int)$argv[7];
	$data = json_decode($argv[8], true);

	$nsc = login($username, $password, $wsdl_path, $timeout);
	$rv = NULL;

	try {
		switch($func) {
			case 'get_query':
				$rv = get_query($data['query'], $data['category'],
                    arr_get($data, 'start', null), arr_get($data, 'count', null));
				break;
			case 'get_account':
				$rv = get_acct($id=arr_get($data,'acct_id'), $ref=arr_get($data,'ref'));
                break;
            case 'get_journal_entries':
                $rv = journal_entries($data['ref'], $data['startDate'], $data['endDate'], $data['types']);
                break;
            case 'get_gifts':
                $rv = journal_entries($data['ref'], $data['startDate'], $data['endDate'], [5]);
                break;
			case 'get_block_size':
				$rv = get_block_size($data['category'], $data['query']);
				break;
			case 'get_route_size':
				$rv = get_route_size($data['category'], $data['query'], $data['date']);
				break;
			case 'get_next_pickup':
				$rv = get_next_pickup($data['email']);
				break;
			case 'find_acct_by_phone':
				$rv = find_acct_by_phone($data['phone']);
				break;
            case 'donor_history':
                $rv = journal_entries($data['ref'], $data['startDate'], $data['endDate'], [1,5]);
                break;
            case 'getQueryResultStats':
                $rv = getQueryResultStats($data['queryName'], $data['queryCategory']);
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
			case 'add_gifts':
				if($sandbox) {$rv = sandbox_err($func); break;}
				$rv = add_gifts($data['entries']);
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
        //debug_log(sprintf("func=%s, status=SUCCESS [%f]", $func, end_timer($t1));
		//debug_log('status=SUCCESS, func="' . $func . '" [' . end_timer($t1) . 's]');

		echo json_encode([
		  'status'=>'SUCCESS',
		  'result'=>$rv]);

		$nsc->call("logout");
		exit;
	}
?>
