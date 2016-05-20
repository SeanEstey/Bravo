<?php

//-----------------------------------------------------------------------
function write_log($msg) {
	global $LOG_FILE;
	global $association;

	$line = '[' . date('m-j G:i') . ' php ' . strtoupper($association) . ']: ' . $msg . "\n";

	// IMPORTANT: this function requires execute permissions on the folder to write!!
	file_put_contents($LOG_FILE, $line, FILE_APPEND);

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
