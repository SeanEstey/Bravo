<?php
require("/root/bravo/php/lib/nusoap.php");

//-----------------------------------------------------------------------
function is_error($nsc) {
    /* Checks SOAP obj for API call errors */
    $err = ($nsc->fault || $nsc->getError()) ? true : false;
    if($err)
        http_response_code(500);
    return $err;
}

//-----------------------------------------------------------------------
function get_error($nsc, $log=true) {
    if(!$nsc->fault)
        $err_desc = 'Error: ' . $nsc->getError();
    else
        $err_desc = 'Error ' . $nsc->faultcode . ". " . $nsc->faultstring;
    if($log)
      error_log($err_desc);
    return $err_desc;
}

//-----------------------------------------------------------------------
function get_endpoint($user, $pass) {
  $endpoint = "https://sna.etapestry.com/v3messaging/service?WSDL";
  $nsc = new nusoap_client($endpoint, true);

  if(is_error($nsc))
			return get_error($nsc, $log=True);

  $newEndpoint = $nsc->call('login', array($user, $pass));
	if(is_error($nsc))
			return get_error($nsc, $log=True);

  if($newEndpoint != "") {
			error_log("Given endpoint failed. Using '" . $newEndpoint . "'");

			$nsc = new nusoap_client($newEndpoint, true);

      if(is_error($nsc))
          return get_error($nsc, $log=True);

			$nsc->call("login", array($user, $pass));

      if(is_error($nsc))
          return get_error($nsc, $log=True);
  }
  return $nsc;
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
function sandbox_err($func) {
    return 'sandbox mode blocked func="' . $func . '" to prevent write(s) to eTap';
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

?>
