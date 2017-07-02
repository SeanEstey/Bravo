<?php

require("/root/bravo/php/lib/nusoap.php");
require("/root/bravo/php/lib/nusoap_wsdlcache.php");

//-----------------------------------------------------------------------
function login($user, $pass, $wsdl_path, $timeout) {
    /* Acquire SOAP endpoint from WSDL file and login w/ user credentials.
    */

    $wsdl_location = realpath($wsdl_path);
    $wsdl_cache = new nusoap_wsdlcache("/tmp"); // for caching purposes
    $wsdl_obj = $wsdl_cache->get($wsdl_location);

    if (empty($wsdl_obj)) {
      $wsdl_obj=new wsdl($wsdl_location);
      $wsdl_cache->put($wsdl_obj);
    }

    $nsc = new nusoap_client($wsdl_obj,true,false,false,false,false,0,$timeout);

	if(is_error($nsc))
		return get_error($nsc, $log=True);

	$wsdl_url = $nsc->call('login', array($user, $pass));

	if($wsdl_url != "") {
		debug_log("Redirected to new WSDL url");
		$nsc = new nusoap_client($wsdl_url,true,false,false,false,false,0,$timeout);
		$nsc->call("login", array($user, $pass));
        return $nsc;
	}
    else
        return $nsc;

	//$nsc = new nusoap_client($wsdl_url, true, false, false, false, false, 0, $timeout);
}

//-----------------------------------------------------------------------
function is_error($nsc) {
    /* Checks SOAP obj for API call errors */
    return $nsc->fault || $nsc->getError() ? true : false;
}

//-----------------------------------------------------------------------
function get_error($nsc, $log=false) {

    if(!is_error($nsc))
        return "";

    $num_format_exc = "NumberFormatException";

    if(!$nsc->fault){
        $desc = $nsc->getError();
    }
    else {
        $desc = "Fault error: " . $nsc->faultstring;

        if(strpos($desc, $num_format_exc) > -1)
            $desc = "Fault error. Incorrect format" . substr($desc, strpos($desc, $num_format_exc) + strlen($num_format_exc));
    }

    if($log == true)
      debug_log($desc);

    return $desc;
}

//-----------------------------------------------------------------------
function reset_error($nsc) {
	$nsc->fault = NULL;
	$nsc->faultcode = NULL;
	$nsc->error_str = NULL;
}

//-----------------------------------------------------------------------
function get_udf($acct, $field) {
    /* Return list of values for matching DefinedValue object(s), false if
       none found
     * @field: DefinedValue['fieldName']
    */

    $values = [];
    foreach($acct['accountDefinedValues'] as $idx=>$dv) {
        if((string)$field == $dv['fieldName'])
            $values[] = $dv['value'];
    }
    if(count($values) == 1)
        return $values[0];
    else if(count($values) > 1)
        return $values;
    else
        return false;
}

//-----------------------------------------------------------------------
function format_date($dateStr) {
    /* Convert dd/mm/yyyy str to native eTap datetime
       Returns str msg on invalid format error.
    */

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
function sandbox_err($func) {
    return 'sandbox mode blocked func="' . $func . '" to prevent write(s) to eTap';
}

?>
