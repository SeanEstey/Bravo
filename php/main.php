<?php

//-----------------------------------------------------------------------
function get_acct($id=NULL, $ref=NULL) {

	global $nsc;
    $acct = NULL;

    if(!is_null($id)) {
        $acct = $nsc->call("getAccountById", array($id));
    }
    else if(!is_null($ref)) {
        $acct = $nsc->call('getAccount', array($ref));
    }

    if(!$acct) {
        $id_or_ref = $id . $ref;
        throw new Exception('no acct matching id/ref ' . $id_or_ref);
    }

    if(is_error($nsc))
        throw new Exception(get_error($nsc, $log=true));
    return utf8_converter($acct);
}

//-----------------------------------------------------------------------
function get_accts($acct_ids=NULL, $acct_refs=NULL) {

	ini_set('max_execution_time', 30000); // IMPORTANT: To prevent fatal error timeout
	global $nsc;
    $list = NULL;
    $accts = [];

    if(!is_null($acct_ids))
        $list = $acct_ids;
    else if(!is_null($acct_refs))
        $list = $acct_refs;

    for($i=0; $i< count($list); $i++) {
        try {
            if(!is_null($acct_ids))
                $accts[] = get_acct($id=$list[$i], NULL);
            else if(!is_null($acct_refs))
                $accts[] = get_acct(NULL, $ref=$list[$i]);
        } catch (Exception $e) {
            $accts[] = ["ref"=>null, "message"=>(string)$e];
            reset_error($nsc);
        }
    }
    return $accts;
}

//-----------------------------------------------------------------------
function get_query($query, $category) {

	global $nsc;
    $rv = $nsc->call("getExistingQueryResults", [[
        'start' => 0,
        'count' => 500,
        'query' => "$category::$query"
      ]]
    );

    if(is_error($nsc))
		return 'query ' . $query . ', category ' . $category;

    debug_log($rv['count'] . ' accounts in query ' . $query);
    return utf8_converter($rv);
}

//-----------------------------------------------------------------------
function find_acct_by_phone($phone) {
	/* Searches accounts for matching User Defined Field 'SMS', which
	 * is filled in by Bravo if an accounts Persona has a valid Mobile Phone.
	 * Field is international format: +14035551111
	 * @phone: international format phone number
	 * Returns: eTap Account object on success, false on no result.
	 */

	global $nsc;
	//debug_log('finding account for ' . $phone);

	$dv = ['fieldName'=>'SMS', 'value'=> $phone];
	$acct = $nsc->call('getAccountByUniqueDefinedValue', array($dv));

	if(is_error($nsc))
		return get_error($nsc, $log=true);

	if(!$acct)
		throw new Exception('no acct found with SMS field="' . $phone . '"');

	//debug_log('found acct_id=' . $acct['id'] . ' matching ' . $phone);
	return utf8_converter($acct);
}

//-----------------------------------------------------------------------
function get_route_size($category, $query, $date) {
	/* Find out how many stops in given Query are scheduled for given Date
	 * @date: eTap formatted date string dd/mm/yyyy
	 * Returns: string "booked/total",
	 */

	global $nsc;
	ini_set('max_execution_time', 30000); // IMPORTANT: To prevent fatal error timeout
  
	$response = $nsc->call("getExistingQueryResults", [[ 
	'start' => 0,
	'count' => 500,
	'query' => "$category::$query"
	]]);

	// Often "invalid query" or "invalid category"
	if(is_error($nsc)) {
		$msg = get_error($nsc, $log=false);
		return $msg . ' (query="' . $query . '", category="' . $category .'")';
	}

	// Convert from str dd/mm/yyyy to date object
	$date = explode("/", $date);
	$date = implode('/', [$date[1],$date[0],$date[2]]);
	$date = strtotime($date);
  
	$matches = 0;

	foreach($response['data'] as $acct) {
		$blocks = [];
		$next_pickup = '';
		$next_delivery = '';
	
		// Extract UDF's
		foreach($acct['accountDefinedValues'] as $udf) {
			if($udf['fieldName'] == 'Next Pickup Date') {
				// Convert from str dd/mm/yyyy to date object
				$next_pickup = explode("/", $udf['value']);
				$next_pickup = implode('/', [$next_pickup[1],$next_pickup[0],$next_pickup[2]]);
				$next_pickup = strtotime($next_pickup);
			}
			else if($udf['fieldName'] == 'Next Delivery Date') {
				$next_delivery = explode("/", $udf['value']);
				$next_delivery = implode('/', [$next_delivery[1],$next_delivery[0],$next_delivery[2]]);
				$next_delivery = strtotime($next_delivery);
			}
			else if($udf['fieldName'] == 'Block')
				$blocks[] = $udf['value'];
		}

		// Pickup Date can be earlier than given date and still a match
		// i.e. we're looking up a weekly business a month from now.
		if($next_pickup && $next_pickup <= $date)
			$matches++;
		else if($next_delivery && $next_delivery == $date)
			$matches++;
	  }

	$ratio = (string)$matches . '/';

	if(isset($response['count']))
		$ratio .= (string)$response['count'];
	else
		$ratio .= '?';

	//debug_log($query . ' ' . date("M j, Y", $date) . ': ' . $ratio);
	return $ratio;
}

//-----------------------------------------------------------------------
function get_block_size($query_category, $query) {
	/* Return number of accounts in given query
	 */

	global $nsc;
	$response = $nsc->call('getExistingQueryResults', [[
		'start' => 0,
		'count' => 500,
		'query' => "$query_category::$query"
		]]);

	if(is_error($nsc)) {
		throw new Exception(get_error($nsc, $log=false));
	}

	debug_log('Query ' . $query . ' count: ' . $response['count']);
	return $response['count'];
}

//-----------------------------------------------------------------------
function batch_journal_entries($refs, $start, $end, $types) {

	global $nsc;
	ini_set('max_execution_time', 30000); // IMPORTANT: prevents timeout err
    $rv = [];

    for($i=0; $i<$count($refs); $i++) {
        try {
            $rv[] = [
                'status'=>'success',
                'je'=>journal_entries($refs[$i], $start, $end, $types)
            ];
        }
        catch(Exception $e) {
            $rv[] = [
                'status'=>'failed',
                'description'=>(string)$e
            ];
        }

        if(is_error($nsc)) {

            reset_error($nsc);
        }
    }
}

//-----------------------------------------------------------------------
function journal_entries($ref, $start, $end, $types) {
	/* @ref: acct ref
     * @start, @end: filter date str's in dd/mm/yyyy
     * @types: array of JE types (note=1, gift=5)
	 */

	global $nsc;
	ini_set('max_execution_time', 30000); // IMPORTANT: prevents timeout err

	$request = [
		'accountRef' => $ref,
		'start' => 0,
		'count' => 100,
		'startDate' => format_date($start),
		'endDate' => format_date($end),
		'types' => $types
	];

	$response = $nsc->call("getJournalEntries", array($request));

	if(is_error($nsc))
		return get_error($nsc, $log=true);
    
    return $response['data'];
}

//-----------------------------------------------------------------------
function get_receipts($acct_ref, $start, $end) {

	global $nsc;

    $entries = journal_entries($acct_ref, $start, $end, [5]);

	if(is_error($nsc))
		return get_error($nsc, $log=true);

    $receipt_entries = null;

    for($i=0; $i<count($entries); $i++) {
		if(array_key_exists('receipt', $entries[$i])) {
            $receipt_entries[] = $entries[$i];
        }
    }

    debug_log(count($receipt_entries) . ' receiptable gifts retrieved.');

    return $receipt_entries;
}

//-----------------------------------------------------------------------
function gift_histories($acct_refs, $start, $end) {
    /* For each acct ref, retrieves Gift Objects between dates, returns
     * "date" and "amount" fields where amount > $0.00
     */

    set_time_limit(600);
	ini_set('max_execution_time', 30000); // Prevents timeout err
	global $nsc;
    $accts_je = [];

    for($i=0; $i<count($acct_refs); $i++) {
        $entries = journal_entries($acct_refs[$i], $start, $end, [5]);
        $pos_gifts = [];

        for($j=0; $j<count($entries); $j++) {
            $entry = $entries[$j];

            if($entry['amount'] > 0) {
                $pos_gifts[] = [
                    'ref' => $acct_refs[$i],
                    'amount' => floatval($entry['amount']),
                    'date' => $entry['date']];
            }
        }

        $accts_je[] = $pos_gifts;
    }

    debug_log(count($accts_je) . ' gift histories retrieved.');

    return $accts_je;
}

//-----------------------------------------------------------------------
function process_entries($entries) {
	/* Updates UDF's and upload gifts for given accts
	@entries: 2d array: [
        "acct_id":"int>",
        "udf"=>["Field Name 1"=>"Field Value", ... ],
        "gift"=>["date"=>"<str>", "amount"=>"<float>"]]
	Returns 2d array of results: [
        "row"=>"<int>", "status"=>"<str>", "description"=>"<err_str>"]
	*/

    ini_set('max_execution_time', 30000); // For timeout error
    global $nsc, $agcy;
    $entries = json_decode(json_encode($entries), true); // stdclass->array
    $n_errs = $n_success = 0;
    $n_entries = count($entries);
    $rv = [];
    debug_log('processing entries for ' . (string)$n_entries . ' accts (agcy=' . $agcy . ')...');

    for($i=0; $i<$n_entries; $i++) {
        reset_error($nsc);
        $entry = $entries[$i];
        $row = $entry['ss_row'];

        try {
            $acct = get_acct($id=$entry['acct_id']);
        } catch(Exception $e) {
            $status = 'no acct found for ID="' . $entry['acct_id'] . '"';
            $rv[] = ['row'=>$row, 'status'=>'Failed', 'description'=>$status];
            debug_log($status);
            $n_errs++;
            continue;
        }

        //if(!empty($entry['gift']['date']))
        remove_udf($acct, $entry['udf']);

        apply_udf($acct, $entry['udf']);

		if(is_error($nsc)) {
            $rv[] = [
                'row'=>$row,
                'status'=>'Failed',
                'description'=>'Update error: ' . get_error($nsc)
            ];
            $n_errs++;
            debug_log(print_r(end($rv),true));
			continue;
		}

		if(empty($entry['gift']['amount']) && $entry['gift']['amount'] !== 0) {
			$rv[] = ['row'=>$row, 'status'=>'Updated'];
			continue;
		}

		try {
			$ref = upload_gift($entry, $acct);
		} catch (Exception $e) {
			$rv[] = [
				'row'=>$row,
				'status'=>'Failed',
				'description'=>get_error($nsc)];
            $n_errs++;
            debug_log(print_r(end($rv),true));
			continue;
		}

        if(is_error($nsc)) {
            $rv[] = [
				'row'=>$row,
				'status'=>'Failed',
				'description'=>get_error($nsc)];
            $n_errs++;
            debug_log(print_r(end($rv),true));
        }
        else {
            if(floatval($ref) == 0)
                debug_log('invalid db ref="' . $ref . '"');

            debug_log(json_encode(['row'=>$row, 'ref'=>$ref]));
            $rv[] = ['row'=>$row, 'status'=>'Processed'];
            $n_success++;
        }
    }

    debug_log($n_entries . ' entries processed. n_success=' . $n_success . ', n_errors=' . $n_errs);
    reset_error($nsc);

	return [
		'n_success'=>$n_success,
		'n_errs'=>$n_errs,
		'results'=>$rv];
}

//-----------------------------------------------------------------------
function upload_gift($entry, $acct) {

	global $nsc, $agcy;

    if($agcy == 'vec') {
        $entry['gift']['definedValues'] = [[
          'fieldName' => 'T3010 code',
          'value' => '4000-560'
        ]];
    }
    else {
        // GG deliveries are blank
        if(empty($entry['gift']['amount']))
            if($entry['gift']['amount'] !== 0)
                return;
        $entry['gift']['definedValues'] = [];
    }

    return $nsc->call("addGift", [[
      'accountRef' => $acct['ref'],
      'amount' => $entry['gift']['amount'],
      'fund' => $entry['gift']['fund'],
      'campaign' => $entry['gift']['campaign'],
      'approach' => $entry['gift']['approach'],
      'note' => $entry['gift']['note'],
      'date' => format_date($entry['gift']['date']),
      'valuable' => [
        'type' => 5,
        'inKind' => []
      ],
      'definedValues' => $entry['gift']['definedValues']
    ],
      false
    ]);
}

//-----------------------------------------------------------------------
function add_note($acct_id, $date, $body) {
    /* Add Journal Note
     * Returns: note db_ref num on success
     */

	global $nsc;
    $acct = get_acct($id=$acct_id);
    $trans = [
      'accountRef' => $acct['ref'],
      'note' => $body,
      'date' => format_date($date)];

    $ref = $nsc->call("addNote", array($trans, false));

    if(is_error($nsc))
        return get_error($nsc, $log=True);
    
    //debug_log('note added (acct_id=' . $acct_id . ')');
    return ["ref"=>$ref];
}

//-----------------------------------------------------------------------
function update_note($acct_id, $ref, $body) {

	global $nsc;
    $note = $nsc->call('getNote', array($ref));
    if(is_error($nsc))
        return get_error($nsc, $log=True);

    $note['note'] = $body;
    $update_ref = $nsc->call('updateNote', array($note, false));
    if(is_error($nsc))
        return get_error($nsc, $log=True);
    
    debug_log('note updated (acct_id=' . $acct_id . ')');
    return ["ref"=>$update_ref];
}

//-----------------------------------------------------------------------
function add_accts($entries) {
    /* Returns: Array of ['row'=>INT, 'status'=>STR, 'ref'=>STR] for each
     * acct created.
     */

	global $nsc, $agcy;
    $entries = json_decode(json_encode($entries), true); // stdclass->array
	//$entries = json_decode($entries, true);
    $n_errs = $n_success = 0;
    $rv = [];
	debug_log('adding ' . count($entries) . ' accounts...');
  
	for($n=0; $n<count($entries); $n++) {
        $entry = $entries[$n];

        // Clear empty UDF fields (i.e. Office Notes may be blank)
        foreach($entry['udf'] as $key=>$value) {
          if(empty($value))
              $entry['udf'] = remove_key($entry['udf'], $key);
        }

        // Modify existing eTap account
        if(!empty($entry['existing_account'])) {
            $status = modify_acct( 
                $entry['existing_account'], 
                $entry['udf'], 
                $entry['persona']);

            if($status != 'Success') {
                $rv[] = ['row'=>$row, 'status'=>$status];
                $n_errs += 1;
                reset_error($nsc);
            }
            else {
                $rv[] = ['row'=>$row, 'status'=>$status];
                $n_success += 1;
            }
          continue;
        }

        // Create new account
        $acct = $entry['persona'];
        $udf = $entry['udf'];

        foreach($udf as $key=>$value) {
            if($key != 'Block' && $key != 'Neighborhood') {
                $acct['accountDefinedValues'][] = [
                    'fieldName'=>$key,
                    'value'=>$value];
            }
            else {
                $list = explode(",", $value);
                for($j=0; $j<count($list); $j++) {
                    if($list[$j])
                        $acct['accountDefinedValues'][] = ['fieldName'=>$key, 'value'=>$list[$j]];
                }
            }
        }

        $status = $nsc->call("addAccount", array($acct, false));

        if(is_error($nsc)) {
            $n_errs += 1;
            $desc = get_error($nsc, $log=false);
            $rv[] = ['row'=>$entry['ss_row'], 'status'=>$desc];
            debug_log('error adding account ' . $acct['name'] . '. desc: ' . $desc);
            reset_error($nsc);
        }
        else {
            $n_success += 1;
            $rv[] = ['row'=>$entry['ss_row'], 'status'=>'COMPLETED', 'ref'=>$status];
            debug_log('added account ' . $acct['name']);
        }
	}

	debug_log((string)$n_success . ' accts added/updated. ' . (string)$n_errs . ' errors.');
    reset_error($nsc);

	return [
		'n_success'=>$n_success,
		'n_errs'=>$n_errs,
		'results'=>$rv];
}

//-----------------------------------------------------------------------
function modify_acct($id, $udf, $persona) {
	/* Modify an acct Persona and/or User Defined Fields
     * @persona, @udf: associative arrays of FieldName=>Value (not DefinedValue objects)
     */

	global $nsc;
	$acct = get_acct($id=$id);

    foreach($persona as $key=>$value) {
      // If 'phones' array is included, all phone types must be present or data will be lost
      $acct[$key] = $value;
    }

    // Fix blank firstName / lastName bug in non-business accounts
    if($acct['nameFormat'] != 3)  {
      if(!$acct['lastName'] || !$acct['firstName']) {
        $split = explode(' ', $acct['name']);
        $acct['firstName'] = $split[0];
        $acct['lastName'] = $split[count($split)-1];
      }
    }

    $nsc->call("updateAccount", [$acct, false]);

    if(is_error($nsc))
        return get_error($nsc, $log=True);

    remove_udf($acct, $udf);
    apply_udf($acct, $udf);

    if(is_error($nsc))
        return get_error($nsc, $log=True);

    //debug_log('updated acct_id=' . $id);
    return 'Success';
}

//-----------------------------------------------------------------------
function skip_pickup($acct_id, $date, $next_pickup) {
	/* Updates UDF's, adds JE note, return confirm. string
	 * @date, @next_pickup: dd/mm/yyyy str
	 */

	global $nsc;
	$acct = get_acct($id=$acct_id);
	$off_notes = get_udf($acct, 'Office Notes') . ' No Pickup ' . $date;

	apply_udf($acct, [
			'Office Notes'=>$off_notes,
			'Next Pickup Date'=>$next_pickup]);

	// params: Note Obj, createFieldAndValues (bool)
	$status = $nsc->call("addNote", [[
		'accountRef' => $acct['ref'],
		'note' => 'No Pickup',
		'date' => format_date($date)
		],
		false
	]);
	
	//debug_log('skipping pickup, acct_id=' . $acct_id);
	return json_encode(["No Pickup request received. Thanks"]);
}

//-----------------------------------------------------------------------
function remove_udf($acct, $udf) {
	/* Clear all the User Defined Field values
	 * $udf: array of defined field names
	 * $acct: eTap account
	 */

	global $nsc;
	$udf_remove = [];

	// Cycle through numbered array of all UDF values. Defined Fields with
	// multiple values like checkboxes will contain an array element for each value
	foreach($acct['accountDefinedValues'] as $key=> $field) {
		if($field['fieldName'] == 'Data Source' || 
		   $field['fieldName'] == 'Are you ready to start collecting empty beverage containers?' || 
 		   $field['fieldName'] == 'Beverage Container Customer' || 
		   $field['fieldName'] =='Next PickUp Date' || 
		   $field['fieldName'] == 'Mailing Address' || 
		   $field['fieldName'] == 'Location Type' || 
		   $field['fieldName'] == 'Pick Up Frequency') {
		       $udf_remove[] = $acct['accountDefinedValues'][$key];
			   continue;
		}

		if(array_key_exists($field['fieldName'], $udf))
	  		$udf_remove[] = $acct["accountDefinedValues"][$key];       
	}

	if(empty($udf_remove))
		return false;

	$nsc->call('removeDefinedValues', array($acct["ref"], $udf_remove, false));

	if(is_error($nsc))
		return get_error($nsc, $log=true);
}

//-----------------------------------------------------------------------
function apply_udf($acct, $udf) {
	/* Converts associative array of defined values into DefinedValue eTap 
	 * object, modifies account
	 * $udf: associative array of udf_names=>values
	 * $account: eTap Account object
	 */

	global $nsc;
	$definedvalues = [];
  
	foreach($udf as $fieldname=>$fieldvalue) {
		if(!$fieldvalue)
			continue;
		else if(($fieldname == 'Block' || $fieldname == 'Neighborhood') && strpos($fieldvalue, ',') !== FALSE) {
			// Multi-value UDF's (Neighborhood, Block) need array for each value 
		  	$split = explode(',', $fieldvalue);
		  
		    foreach($split as $e) {
				$definedvalues[] = ['fieldName'=>$fieldname, 'value'=>$e];
			}
		}
		else {
			$definedvalues[] = ['fieldName'=>$fieldname, 'value'=>(string)$fieldvalue];
		}
	}

	if(empty($definedvalues))
		return false;

	$nsc->call('applyDefinedValues', array($acct["ref"], $definedvalues, false));
	if(is_error($nsc))
		return get_error($nsc, $log=true);
}

//-----------------------------------------------------------------------
function check_duplicates($persona_fields) {

	global $nsc;
	$accts = $nsc->call("getDuplicateAccounts", array($persona_fields));
  
	if(is_error($nsc))
		return get_error($nsc, $log=true);

	if(empty($accts))
		return false;

    $ids = [];
	for($i=0; $i<sizeof($accts); $i++) {
		$ids[] = $accts[0]['id'];
    }

    debug_log("Found " . (string)sizeof($accts) . " duplicate accounts");

    return $ids;
}

//-----------------------------------------------------------------------
function make_booking($acct_id, $udf, $type) {
	/* Type: either 'pickup' or 'delivery' */

	global $nsc, $agcy;
	$acct = get_acct($id=$acct_id);
  
	// convert stdclass to array
	if(is_object($udf)) {
		$udf = get_object_vars($udf);
	}

	$udf['Driver Notes'] = get_udf($acct, 'Driver Notes') . '\\n' . $udf['Driver Notes'];
	$off_notes = get_udf($acct, 'Office Notes');
	$blocks = get_udf($acct, 'Block');

    if(!is_array($blocks))
        $blocks = [$blocks];

	// Omit ***RMV BLK*** if book block == natural block
	if(in_array($udf['Block'], $blocks))
		$udf['Office Notes'] = $off_notes;
	else
		$udf['Office Notes'] =  $off_notes . '\\n' . $udf['Office Notes'];

	if($agcy == 'wsf' && $type == 'delivery') {
		$status = get_udf($acct, 'Status');

		if($status != 'Active' || $status != 'Dropoff' || $status != 'Cancelling')
			$udf['Status'] = 'Green Goods Delivery';
		else if(!$status)
			$udf['Status'] = 'Green Goods Delivery';
	}

	apply_udf($acct, $udf);

	if(is_error($nsc))
		return get_error($nsc, $log=true);

	debug_log('Booked Account #' . $acct_id . ' on Block ' . $udf['Block']);
	return 'Booked successfully!';
}

//-----------------------------------------------------------------------
function get_next_pickup($email) {
	/* Find account matching given Email and get it's "Next Pickup Date" 
	 * User Defined Field. Called from emptiestowinn.com
	 * Returns: dd/mm/yyyy string on success, false if account not found
	 * or empty Next Pickup Date field
	 */

	global $nsc;
	$dv = [
		'email' => $email,
		'accountRoleTypes' => 1,
		'allowEmailOnlyMatch' => true]; 
	$acct = $nsc->call("getDuplicateAccount", array($dv));

	if(empty($acct))
		throw new Exception('acct not found for ' . $email);

	// Loop through array and extract fieldName = "Next Pickup Date"
	foreach($acct as $search) {
		if(!is_array($search))
			continue;

		foreach($search as $searchArray) {
			extract($searchArray);
			if($fieldName == 'Next Pickup Date') {
				debug_log('Next Pickup for ' . $email . ': ' . format_date($value));
				return format_date($value);
			}
		}
	}
	throw new Exception('invalid/missing pickup date for acct_id=' . $acct);
}

?>
