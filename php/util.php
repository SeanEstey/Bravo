<?php

$DEBUG_LOG = '/root/bravo/logs/debug.log';
$INFO_LOG = '/root/bravo/logs/events.log';
$ERROR_LOG = '/root/bravo/logs/events.log';
$COLORS = array(
	// styles
	// italic and blink may not work depending of your terminal
	'bold' => "\033[1m%s\033[0m",
	'dark' => "\033[2m%s\033[0m",
	'italic' => "\033[3m%s\033[0m",
	'underline' => "\033[4m%s\033[0m",
	'blink' => "\033[5m%s\033[0m",
	'reverse' => "\033[7m%s\033[0m",
	'concealed' => "\033[8m%s\033[0m",
	// foreground colors
	'black' => "\033[30m%s\033[0m",
	'red' => "\033[91m%s\033[0m",
	'green' => "\033[32m%s\033[0m",
	'yellow' => "\033[93m%s\033[0m",
	'blue' => "\033[94m%s\033[0m",
	'magenta' => "\033[35m%s\033[0m",
	'cyan' => "\033[36m%s\033[0m",
	'white' => "\033[37m%s\033[0m",
	// background colors
	'bg_black' => "\033[40m%s\033[0m",
	'bg_red' => "\033[41m%s\033[0m",
	'bg_green' => "\033[42m%s\033[0m",
	'bg_yellow' => "\033[43m%s\033[0m",
	'bg_blue' => "\033[44m%s\033[0m",
	'bg_magenta' => "\033[45m%s\033[0m",
	'bg_cyan' => "\033[46m%s\033[0m",
	'bg_white' => "\033[47m%s\033[0m",
);

//-----------------------------------------------------------------------
function start_timer() {
    return round(microtime(true) * 1000);
}

//-----------------------------------------------------------------------
function end_timer($t1) {
    $now_ms = start_timer();
    return ($now_ms - $t1)/1000;
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

    global $DEBUG_LOG, $COLORS;
	$str = sprintf($COLORS['white'], $msg);
    return write_log($str, $DEBUG_LOG);
}

//-----------------------------------------------------------------------
function err_log($msg) {
    /* Convenience func */

    global $ERROR_LOG, $COLORS;
	$str = sprintf($COLORS['red'], $msg);
    return write_log($str, $ERROR_LOG);
}

//-----------------------------------------------------------------------
function write_log($msg, $path) {
	/* file_put_contents required execution permission on log folder */

    global $agcy, $COLORS;
	$format = '[' . date('m-j G:i') . ' php]: ';
    $format = sprintf($COLORS['blue'], $format);
    file_put_contents(
		$path,
		$format . $msg . "\n",
		FILE_APPEND);
    return json_encode($msg);
}

//-----------------------------------------------------------------------
function utf8_converter($array) {
	/* Get rid of non-UTF chars which cause python errors */

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
