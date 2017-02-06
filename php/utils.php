<?php

$INFO_LOG = '/var/www/bravo/logs/info.log';
$DEBUG_LOG = '/var/www/bravo/logs/debug.log';
$ERROR_LOG = '/var/www/bravo/logs/error.log';

//-----------------------------------------------------------------------
function info_log($msg) {
    /* Convenience func */
    global $INFO_LOG;
    return write_log($msg, $INFO_LOG);
}

//-----------------------------------------------------------------------
function debug_log($msg) {
    /* Convenience func */
    global $DEBUG_LOG;
    return write_log($msg, $DEBUG_LOG);
}

//-----------------------------------------------------------------------
function write_log($msg, $log_path) {
    global $agcy;
    $line = '[' . date('m-j G:i') . ' php ' . $agcy . ']: ' . $msg . "\n";
    // IMPORTANT: requires execute permissions on the folder to write!!
    file_put_contents($log_path, $line, FILE_APPEND);
    return json_encode($msg);
}

/*** General PHP Helper Functions ***/

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
