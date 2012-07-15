# Book Search

Very simple book search, based in [isbndb.com][isbndb] [Google Books][] and [Werkzeug][werkzeug].

## Install

Look at dependences and install them before running the `app.py` file.

	$ python app.py
	* Running on http://127.0.0.1:5000/                                                                                  
	* Restarting with reloader  

You get the application running in `localhost:5000`


## Internals

The application has 3 parts in a MVC way. Classes in `api.py` and `search.py` grabs and manipulate
the data, for `app.py` to manage it and the templates and `jQuery` code to make the view logic.

## app.py

The web application itself. It can be accessed through the following urls:
	
	/                        (index)
	/b/{by}/{query}          (search by isbn/author...)
	/b/{by}/{query}/{page}   (search by isbn/author... at certain page)

The index page contains a search box which will retrieve all the needed results.

## search.py

Layer on top of `api.py` to perform searches. It exposes a search interface to perform easy
requests searching books by a certain `field` and retrieving the covers without having to bother
with the `Requests` objects. It also cares about paralellism so most of the calls that can be done
at the same time are made.

	>>> s = Search(by='title', query='rayuela').get()
	>>> for b in s.books:
			print (b.title, b.authors)

	('Criaturas ficticias y su mundo, en Rayuela de Cortazar', ['Brita Brodin'])
	(u'Cuaderno de bit\xe1cora de "Rayuela"', [u'Julio Cort\xe1zar; [estudio preliminar] Ana
	Mar\xeda Barrenechea'])
	('Formen des Offenen: Thomas Manns Zauberberg, die "Oxen of the Sun"-Episode in James Joyces
	Ulysses und Julio Cartazars Rayuela', ['Paul Forssbohm'])
	('Julio Cortazar, Rayuela', ['[by] Robert Brody'])
	('Nahuatl to Rayuela', ['edited & introduced by Dave Oliphant'])
	('Rayuela', ['Julio Cortazar'])
	("Rayuela's Paris", ['Hector Zampaglione'])
	('Rayuela', ['Julio Cortazar'])

## api.py

Holds the main work of fetching the book data. It's composed by several classes that can be used to
perform a certain `Request` to fetch information. Those `Request` are also `Threads` so the
requests can be made in parallel.

The Requests all derive from the `APIRequest` class, which is abstract, implements a `get` method
to actually perform the request whose result can be checked in the `.data` member.

	>>> r = Request(param1='this', param2='that').get()
	>>> r.data
	[<Result at 104824>, <Result at 1039242>]

And using threading:

	>>> requests = [Request(search=s) for s in ('git', 'python', 'werkzeug')] 
	>>> Request.dispatch(requests)  # All requests called in parallel
	>>> [r.data for r in requests]
	[['awesome', 'fast'], 
	  ['elegant', 'nice'], 
	  ['low-level', 'cool']]

- **APIRequest**: Base `Request` class. Performs the HTTP handling, the deserializing of the data
  and it also holds a `Cache` to avoid repeating calls.

- **ISBNdbRequest**: Inherits from `APIRequest` and knows how to compose a request for the
  [isbndb.com][] xml API.

- **GoogleBooksRequest**: Inherits from `APIRequest` and parses the JSON response from the
  [googleapis.com](http://www.googleapis.com) servers. The data included in a `GoogleBooksRequest`
  response is much better than the one in a `ISBNdbRequest` but I just use certain things as the
  main purpose of this application is to try the [isbndb.com][] API. Requests are made by `isbn`.

- **AmazonRequest**: Inherits from `APIRequest` and parses the XML response from the Amazon
  commercial services. Currently not used due to a missing app ID for this application.

The classes listed now inherit from `ISBNdbRequest` and perform the parsing of the xml returned by
the API. The ones different that `BookRequest` doesn't return books, just author/subject/publisher
ids to perform a second search listing books by their ids. 

- **BookRequest**: Basic request for books. Inherits from `ISBNdbRequest` and knows how to parse a
  response from [isbndb.com][] for books. Performs book searches by `title` and `isbn` and also
  listings by `author_id`, `subject_id` and `publisher_id`.

  		>>> r = BookRequest(field='title', value='cryptonomicon').get()
  		>>> r.data
  		[<class 'api.Book'> Baroque Cycle by: Books LLC (Creator),
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon. by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon. by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson, Scott Brick (Narrator),
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson,
		<class 'api.Book'> Cryptonomicon by: Neal Stephenson]

- **AuthorRequest**: Asks for authors. Performs a search by `name` for authors and gets their
  identificators.

- **SubjectRequest**: Searches for certain topics by name to get their ids.

- **PublisherRequest**: Basic request for books. Inherits from `ISBNdbRequest` and knows how to parse a
  response from [isbndb.com][] for books.

## Dependences

Jinja2          - 2.6          
Python          - 2.7.3        
Werkzeug        - 0.8.3        
lxml            - 2.3.4        
wsgiref         - 0.1.2        

[Google Books]: http://www.books.google.com
[isbndb]: http://www.isbndb.com
[werkzeug]: http://werkzeug.pocoo.or
