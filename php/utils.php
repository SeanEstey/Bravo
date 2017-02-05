<?php

require('mongodb_auth.php');

$INFO_LOG = '/var/www/bravo/logs/info.log';
$DEBUG_LOG = '/var/www/bravo/logs/debug.log';
$ERROR_LOG = '/var/www/bravo/logs/error.log';

//-----------------------------------------------------------------------
function get_inputs() {
    global $agcy, $sandbox, $data, $etap_conf, $func;

    // JSON data
    if(!isset($_POST['data'])) {
        $arr = get_object_vars(json_decode(file_get_contents("php://input")));
        
        $func = $arr['func'];
        $data = get_object_vars($arr['data']);
        $etap_conf = get_object_vars($arr['etapestry']);
        $agcy = $etap_conf['agency'];

        if(isset($arr['sandbox']))
            if($arr['sandbox'] == true) {
                debug_log('request made in sandbox mode.');
                $sandbox = true;
            }
    }
    // Form data
    else {
        $func = $_POST['func'];
        $data = json_decode($_POST['data'], true);
        $etap_conf = json_decode($_POST['etapestry'], true);
        $agcy = $etap_conf['agency'];

        if(isset($_POST['sandbox']))
            $sandbox = $_POST['sandbox'];
    }

    #debug_log('agcy=' . $agcy . ', func="' . $func . '"');
}

//-----------------------------------------------------------------------
function get_db() {
    global $mongodb_user, $mongodb_password;
    $db = null;

    try {
        $cred = $mongodb_user . ':' . $mongodb_password; 
        $db = new MongoDB\Driver\Manager('mongodb://'. $cred . '@localhost:27017');
    }
    catch(Exception $e) {
        error_log('mongodb auth error. desc=' . $e->getMessage());
        http_response_code(500);
    }

    return $db;
}
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

//-----------------------------------------------------------------------
function num_php_fpms() {
    $res = [];
    exec("/etc/init.d/php7.0-fpm status | grep 'Processes active'", $res);
    $start_index = strpos($res[0], 'Processes active:') + 17;
    $end_index = strpos($res[0], ',');
    $num_processes = substr($res[0], $start_index, $end_index-$start_index); 
    return $num_processes;
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
