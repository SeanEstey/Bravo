<?php

//-----------------------------------------------------------------------
function utf8_converter($array) {
  array_walk_recursive($array, function(&$item, $key){
    if(!mb_detect_encoding($item, 'utf-8', true)){
      $item = utf8_encode($item);
    }
  });
       
  return $array;
}


//-----------------------------------------------------------------------
function info_log($msg) {
	global $INFO_LOG;
	global $agency;

	$line = '[' . date('m-j G:i') . ' php ' . $agency . ']: ' . $msg . "\n";

	// IMPORTANT: this function requires execute permissions on the folder to write!!
	file_put_contents($INFO_LOG, $line, FILE_APPEND);

	return $msg;
}

//-----------------------------------------------------------------------
function debug_log($msg) {
	global $DEBUG_LOG;
	global $agency;

	$line = '[' . date('m-j G:i') . ' php ' . $agency . ']: ' . $msg . "\n";

	// IMPORTANT: this function requires execute permissions on the folder to write!!
	file_put_contents($DEBUG_LOG, $line, FILE_APPEND);

	return $msg;
}

//-----------------------------------------------------------------------
function default_value($var, $default) {
  return empty($var) ? $default : $var;
}

//-----------------------------------------------------------------------
function add_if_key_exists($dest, $key, $arr) {
  if(array_key_exists($key, $arr))
    $dest[$key] = $arr[$key];
}

//-----------------------------------------------------------------------
function remove_key($array,$key){
    $holding=array();
    foreach($array as $k => $v){
        if($key!=$k){
            $holding[$k]=$v;
        }
    }    
    return $holding;
}

?>
