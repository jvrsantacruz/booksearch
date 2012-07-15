$(document).ready(function(){
  
    // Detail view
    $('#results').delegate('.view-detail', 'click', function(){
      $(this).siblings('.detail').toggle()
    return false;
    })

    // Pages
    $('#results').delegate('.page', 'click', function(){
      search($(this).attr('href'));
      return false;
    })

    // Search
	$('#search-form').submit(search);
})

function search(search_page) {
		var by = $('select.search').val();
		var query = $('input.search').val();
		page = 1;
		if( parseInt(search_page) ) {
		  page = parseInt(search_page);
    }

		if( query.length == 0 ){
		  return false;
    }

		// Show the progress
		$('#results').html($('progress').clone().show());
		$('#results').show();

		// REST url to access to the resource
    var url = encodeURI('/b/' + by + '/' + query + '/' + page);

    $('#results').load(url);
    
		return false;
}
