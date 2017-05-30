/* tools.js */


function tools_init() {

    return; 

    api_call(
      'maps/get',
      data=null,
      function(response){
          var maps = response['data'];

          /*
          $("#user_form [id='first_name']").text(user['name']);
          $("#user_form [id='user_name']").text(user['user_id']);
          $("#user_form [id='is_admin']").text(user['admin']);
          */
      });
}

