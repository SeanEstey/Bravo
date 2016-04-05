
var menu_items = ['HOME', 'PROJECTS', 'CONTACT'];
var MENU_CHANGE_TRIGGER_WIDTH = 550;
var TITLE = 'BRAVO SOFTWARE';

jQuery(function($){
  createMobileMenu();

  // Set initial menu
  if($(document).width() > MENU_CHANGE_TRIGGER_WIDTH)
    renderDesktop();
  else
    renderMobile();

  // Set triggers for menu change on resize
  if (matchMedia) {
    var mq = window.matchMedia("(min-width: 550px)");
    mq.addListener(function(mq) {
      if (mq.matches) {
        console.log('expanded to desktop!');
        renderDesktop();
      }
      else {
        console.log('shrunk to mobile!');
        renderMobile();
      }
    });
  }

  $('#btn-getstarted').click(function() {
    // Can't have the actual ID as the .href property because causes a stutter
    // before the javascript executes
    scrollTo($($(this).attr('href')+'-tag'));
  });

  // Pop-up window when clicking on portfolio thumbnail
  $('.portfolio_box').click(function(event) {
    console.log('show dialog!');
    $('#product-card').show('fade', 1000);
    
    $('#product-card').position({
     my: "center top", 
     at: "center top", 
     of: '.portfolio_box',
     collision: 'none'
    });

    // Prevent click from double registering with document click event
    // handler below
    event.stopPropagation();
  });
   
   
  // If mobile menu active and click is outside bounds, close it.
  // If product-card active and click outside bounds, close it. 
  $(document).click(function(event) {
    if(!$(event.target).closest('#product-card').length) {
      if($('#product-card').is(":visible")) {
        console.log('event.target.className: ' + event.target.className);
        console.log('event.target.id: ' + event.target.id);

        console.log('ancestor of product-card clicked. hiding');
        if(event.target.clo != 'portfolio_content')
          $('#product-card').hide('fade', 1000)
      }
    }
    
    if(!$(event.target).closest('.mobile-menu').length) {
      console.log('outside menu click');
      if($('.mobile-menu').is(':visible'))
        toggleSlidingMenu();
    }
  });

  $('.portfolio_box').mouseenter(function() {
    $(this).find('.recent').show();
  });
  
  $('.portfolio_box').mouseleave(function() {
    $(this).find('.recent').hide();
  });
});


function renderMobile() {
  $('.title h3').replaceWith($("<h4 style='margin:0;'>"+TITLE+"</h4>"));
  showMobileMenuIcon();
}

function renderDesktop() {
  $('.title h4').replaceWith($("<h3 style='margin:0;'>"+TITLE+"</h3>"));
  showHorizontalMenu();
}

/* Build off-screen vertical sliding menu */
function createMobileMenu() {
  $mobile_menu = $("<div class='mobile-menu' hidden></div>");

  for(var i=0; i<menu_items.length; i++) {
    $a = $("<a class='mobile-menu-item' href='#"+menu_items[i].toLowerCase()+"'>"+menu_items[i]+"</a>");
    $a.click(function(e) {
      toggleSlidingMenu();
      scrollTo($($(this).attr('href')+'-tag'));
    });
    $header = $('<h5 style="text-align:right;"></h5>').append($a);
    $item = $('<div></div>').append($header);
    $mobile_menu.append($item);
  }

  $('body').append($mobile_menu);
}


/* Mobile side menu toggle on and off */
function toggleSlidingMenu() {
  $mobile_menu = $('.mobile-menu');
  console.log($(document).height());
  $mobile_menu.css('height', $(document).height());
  if(!$mobile_menu.is(':visible')) { 
    document.body.style.overflow = 'hidden'; // Disable scrolling
    $mobile_menu.show('slide', {direction:'right'}, 250);
  }
  else {
    document.body.style.overflow = 'visible'; // Re-enable scrolling
    $mobile_menu.hide('slide', {direction:'right'}, 250);
  }
}


/* Delete mobile menu icon, replace with horizontal menu items */
function showHorizontalMenu() {
  $('.horizontal-menu').empty();
  $('.horizontal-menu').append('<h5>');
  $('.horizontal-menu').height($('.title').height());

  var divider = "<span class='menu-divider'>||</span>";
  for(var i=0; i<menu_items.length; i++) {
    var $a = $("<a class='menu-item' href='#"+menu_items[i].toLowerCase()+"'>"+menu_items[i]+"</a>");
    $a.click(function(e) {
      scrollTo($($(this).attr('href')+'-tag'));
    });
    $('.horizontal-menu h5').append($a);

    if(i != menu_items.length -1)
      $('.horizontal-menu h5').append(divider);
  }
  $('.horizontal-menu').append('</h5>');
}


/* Delete horizontal menu items, replace with mobile menu icon */
function showMobileMenuIcon() {
  $('.horizontal-menu').empty();
  $('.horizontal-menu').append('<h4>');

  $a = $("<a class='mobile-menu-icon' href='#menu'>   &#9776;   </a>");
  //$a.css('z-index', 3000);
  $a.click(function() {
    event.stopPropagation();
    toggleSlidingMenu();
  });
  $('.horizontal-menu h4').append($a);
}


/* Scroll to # tag */
function scrollTo($dest) {
  $('html, body').animate({
    'scrollTop': $dest.offset().top
  }, 500);
}







