/* app/main/static/js/api.js */

//------------------------------------------------------------------------------
function api_call(path, data, on_done) {
    /* Returns: {
     *   "status": ["success", "failed"],
     *   "data": <str/int/object/array>
     * }
     */
    
    console.log('API call "%s", data=%s', path, JSON.stringify(data));

	$.ajax({
		type: 'POST',
      	data: data,
		url: $URL_ROOT + 'api/' + path})
	.done(function(response){
        on_done(response);
    })
    .fail(function(response){
        on_done(response)});
}
