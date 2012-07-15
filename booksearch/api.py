# -*- coding: utf-8 -*-
"""
Wrapper around the ISBNdb API which provides search functionality.
"""
import re
import json
import hmac
import time
import base64
import urllib
import urllib2
import hashlib
import threading
from functools import wraps
from lxml import objectify, etree
from abc import ABCMeta, abstractmethod

from werkzeug.contrib.cache import SimpleCache

import settings


class APIRequestError(Exception):
    "APIRequest Exception class"
    pass


class ISBNdbRequestError(APIRequestError):
    "ISBNdbRequest Exception class"
    pass


class GoogleBooksRequestError(APIRequestError):
    "ISBNdbRequest Exception class"
    pass


def cached(fn):
    """Decorator to cache function outcomes
    It's better to cache data which has been already processed
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        cache_key = hashlib.sha1("{0}".format((args, kwargs))).hexdigest()

        data = APIRequest.cache.get(cache_key)
        if data is not None:
            return data

        data = fn(*args, **kwargs)

        APIRequest.cache.set(cache_key, data)
        return data

    return wrapper


class APIRequest(threading.Thread):
    """Basic XML GET request
    Abstract class. Derived classes must implement the get() method
    Queries cache their responses after being processed
    Requests are threads so they can be used to perform asynchronous calls
    """

    __metaclass__ = ABCMeta

    cache = SimpleCache(threshold=settings.CACHE_THRESHOLD,
                        default_timeout=settings.CACHE_TIME)

    def __init__(self):
        super(APIRequest, self).__init__()
        self.setDaemon(True)  # Avoid zombie threads when exiting
        self.data = None

    @abstractmethod
    def get(self):
        return self

    def run(self):
        "To be run as a thread"
        self.get()

    @staticmethod
    def distpach(requests):
        "Convenience method for distpaching a list of request threads"
        for r in requests:
            r.start()

        for r in requests:
            r.join()

        return requests

    @classmethod
    def distpach_data(cls, requests):
        """Convenience method for distpaching a list of request threads
        returns the data of each request
        """
        return [r.data for r in cls.distpach(requests)]

    @staticmethod
    def open(url, param=None):
        "Fetchs a remote url using a GET request"
        if param:
            url = "{url}?{params}".format(url=url,
                                          params=urllib.urlencode(param))
        print 'Request: {0}'.format(url)
        try:
            return urllib2.urlopen(url).read()
        except (urllib2.URLError, urllib2.HTTPError), err:
            print 'Error on request: {0}'.format(url)
            raise APIRequestError(err)

    @classmethod
    @cached
    def get_json(cls, url, param=None):
        """Fetch a remote url which returns a deserialized object
        raises APIRequestError on failure
        """
        try:
            return json.loads(cls.open(url, param if param else {}))
        except (TypeError, ValueError, OverflowError), err:
            raise APIRequestError(err)

    @classmethod
    @cached
    def get_xml(cls, url, param=None):
        """Fetch a remote url and parse it's XML object into a DOM object
        returns an lxml.objectify object
        raises APIRequestError on failure
        """
        try:
            return objectify.fromstring(cls.open(url, param if param else {}))
        except etree.XMLSyntaxError, err:
            raise APIRequestError(err)


class GoogleBooksRequest(APIRequest):
    """Google Books API lookup implementation
    Fetchs covers and extra info from books

    It actually performs two requests per book and parses the JSON response:
    1. Search book by isbn
    2. Lookup book to get cover image urls

    Search json response:

            {
                "kind": "books#volumes",
                "totalItems": 22,
                "items": [
                {
                    "kind": "books#volume",
                    "id": "qGlqzgAACAAJ",
                    "etag": "MPfxwSXeREY",
                    "selfLink": "https://www.googleapis.com/books/v1/volumes..
                    "volumeInfo": {
                        "title": "The C programming language",
                        "contentVersion": "full-1.0.0",
                        "language": "en",
                        "previewLink": "http://books.google.es/books?id=qGl...
                        "infoLink": "http://books.google.es/books?id=qGlqzg...
                        "canonicalVolumeLink": "http://books.google.es/book...
                    },
                    "saleInfo": {
                        "country": "ES",
                        "saleability": "FREE",
                        "isEbook": true
                    },
                    "accessInfo": {
                        "country": "ES",
                        "viewability": "NO_PAGES",
                        "embeddable": false,
                        "publicDomain": false,
                        "textToSpeechPermission": "ALLOWED_FOR_ACCESSIBILITY",
                        "epub": {
                        "isAvailable": false
                        },
                        "pdf": {
                        "isAvailable": false
                        },
                        "webReaderLink": "http://books.google.es/books/read...
                        "accessViewStatus": "NONE"
                    }
                }
              ]
            }

        And the lookup response:

        "volumeInfo": {
            "title": "The Google story",
            "authors": [
                "David A. Vise",
                "Mark Malseed"
            ],
            "publisher": "Random House Digital, Inc.",
            "publishedDate": "2005-11-15",
            "description": "\"Here is the story behind one of the most
                                remarkable Internet successes of our time.
                                Based on scrupulous research and extraordinary
                                access to Google, ...",
            "industryIdentifiers": [
                {
                    "type": "ISBN_10",
                    "identifier": "055380457X"
                },
                {
                    "type": "ISBN_13",
                    "identifier": "9780553804577"
                }
            ],
            "pageCount": 207,
            "dimensions": {
            "height": "24.00 cm",
            "width": "16.03 cm",
            "thickness": "2.74 cm"
            },
            "printType": "BOOK",
            "mainCategory": "Business & Economics / Entrepreneurship",
            "categories": [
            "Browsers (Computer programs)",
            ...
            ],
            "averageRating": 3.5,
            "ratingsCount": 136,
            "contentVersion": "1.1.0.0.preview.2",
            "imageLinks": {
                "smallThumbnail": "http://bks1.books.google.com/books?idTCAl...
                "thumbnail": "http://bks1.books.google.com/books?id=zyTCPjgY...
                "small": "http://bks1.books.google.com/books?id=zyTCAlFPC&pr...
                "medium": "http://bks1.books.google.com/books?id=zyTCAlFYC&p...
                "large": "http://bks1.books.google.com/books?id=zyTCAlFPC&pr...
                "extraLarge": "http://bks1.books.google.com/books?id=zyTFPjg...
            },
        (..)
        }

    """

    ACCESS_KEY = settings.GOOGLE_BOOKS_ACCESS_KEY
    BASE_URL = 'https://www.googleapis.com/books/v1/volumes'
    RE_ISBN_10 = re.compile('^((\d|X)[ -]?){10}$')
    RE_ISBN_13 = re.compile('^((\d|X)[ -]?){13}$')

    # Extracted data from the Google request
    FIELDS = ('pageCount', 'averagRating', 'ratingsCount', 'imageLinks')

    def __init__(self, isbn):
        super(GoogleBooksRequest, self).__init__()

        if not self.RE_ISBN_10.match(isbn) and not self.RE_ISBN_13.match(isbn):
            raise GoogleBooksRequestError('Invalid isbn "{0}"'.format(isbn))

        self.params_search = {
            'key': self.ACCESS_KEY,
            'q': 'isbn:{0}'.format(self.clean_isbn(isbn)),
            'maxResults': 1
        }

        # REST-like access for the item lookup
        self.url_lookup = self.BASE_URL + '/{id}'
        self.params_lookup = {
            'key': self.ACCESS_KEY,
        }

        self.json = None

    def get(self):
        """Fetchs the request and initialize self.data
        data will be a dict with part of the info in the lookup response
        containing the fields in FIELDS:
        """
        try:
            if not self.json:
                self.data = {}

                # Perform the search
                self.json = self.get_json(self.BASE_URL, self.params_search)
                if not self.json or self.json['totalItems'] == 0:
                    return self

                book_id = self.json['items'][0]['id']

                # Lookup the book
                self.json = self.get_json(self.url_lookup.format(id=book_id),
                                          self.params_lookup)
                if not self.json or 'volumeInfo' not in self.json:
                    return self

                for field in self.FIELDS:
                    self.data[field] = self.json['volumeInfo'].get(field)
        except APIRequestError:
            self.data = {}

        return self

    def clean_isbn(self, isbn):
        "Removes all non-isbn characters"
        clean = "".join([c for c in isbn if c.isdigit()])
        if isbn[-1].upper() == 'X':
            clean += 'X'
        return clean


class AmazonRequest(APIRequest):
    """Amazon API Book lookup implementation

    Only for book covers
    """

    ACCESS_KEY = settings.AMAZON_ACCESS_KEY
    SECRET_ACCESS_KEY = settings.AMAZON_SECRET_ACCESS_KEY
    HOST = 'webservices.amazon.es'
    PATH = '/onca/xml'
    BASE_URL = 'http://{host}{path}'.format(host=HOST, path=PATH)

    def __init__(self, isbn):
        super(AmazonRequest, self).__init__()

        self.params = {
            'Service': 'AWSECommerceService',
            'AWSAccessKeyId': self.ACCESS_KEY,
            'Operation': 'ItemSearch',
            'AssociateTag': '',
            'SearchIndex': 'Books',
            'Power': 'ISBN:{0}'.format(isbn),
            'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                       time.gmtime())
                      }
        self.dom = None
        self.urls = None

    def get(self):
        """Fetchs the request and initialize self.data
        with a list of urls from smaller to bigger
        """
        if self.dom is None:
            params = urllib.urlencode(self.params)
            params += '&Signature={0}'.format(self._sign_request(self.params))
            self.dom = self.get_xml(self.BASE_URL + '?' + params)

        return self

    def _sign_request(self, params):
        """
        Signs the request's parameters

        Get the canonical url and calculate the SHA1-256 over the base64
        The canonical url is all parameters sorted
        and url-encoded

        Returns the signed parameters

        From the Amazon WS documentation:
            http://docs.amazonwebservices.com/AWSECommerceService
                   /latest/DG/rest-signature.html
        """
        if 'Signature' in params:
            del params['Signature']

        # Prepend this lines to the sorted and escaped url
        canonical = "\n".join(["GET", self.HOST, self.PATH,
                               urllib.urlencode(sorted(params.items()))])

        # Calculate the HMAC-SHA256
        signature = hmac.new(key=self.SECRET_ACCESS_KEY, msg=canonical,
                             digestmod=hashlib.sha256).digest()

        # Base64 the hash
        signature = base64.b64encode(signature)

        # Escape the + and - in the url
        return urllib.quote(signature)


class ISBNdbRequest(APIRequest):
    """ISBNdb API Querying
    Hides the internals to connect to the ISBNdb API.
    Basic example of use:

    >>> req = ISBNdbRequest('books', 'title', 'Nostromo').get()
    >>> req.total_results
    88

    >>> req.page_size
    10

    >> req.page_number
    1

    >>> req.total_pages
    9

    >>> req.more_pages
    True

    >>> len(req.data)
    10

    Another example using the transformation function
    and one extra argument 'results' asking for more information:

    >>> req = (ISBNdbRequest(collection='authors', field='name',\
      value='conrad', trans=lambda dom: dom.Details.get('first_name'),\
      results='details').get())
    >>> req.data[:7]
    ['Conrad', 'Betty', 'Colin', 'Conrad', 'Alan', 'Conrad', 'Conrad']
    """

    ACCESS_KEY = settings.ISBNdb_ACCESS_KEY
    BASE_URL = 'http://isbndb.com/api'
    COLLECTIONS = ('books', 'subjects', 'categories', 'authors', 'publisher')

    def __init__(self, collection, field, value, page=1, trans=None, **kwargs):
        """Request to a given collection filtering by field.
        Page ask for the nth page in the result
        trans is a function which will transform each element in result
          the function should take a single argument, the dom data element of
          the result

        Extra request parameters can be added through kwargs
        """
        super(ISBNdbRequest, self).__init__()
        if collection not in self.COLLECTIONS:
            raise ISBNdbRequestError("Unkown collection '{0}'"
                                     .format(collection))

        self.url = "{base}/{collection}.xml".format(base=self.BASE_URL,
                                                collection=collection)
        self.params = {'access_key': self.ACCESS_KEY, 'index1': field,
                       'value1': value, 'page_number': page}
        self.params.update(kwargs)
        self.trans = trans
        self.dom = None         # dom root element
        self.list_dom = None    # dom of the list of result elements

    def get(self):
        "Fetchs and returns the data"
        if self.dom is None:
            self.dom = self.get_xml(self.url, self.params)

            if self.dom.getchildren():
                self.list_dom = self.dom.getchildren()[0]
                self.data = map(self.trans, self.list_dom.getchildren())

        return self

    @property
    def total_results(self):
        "Returns the total number of results for the API call (listed 10)"
        if self.list_dom is not None:
            return int(self.list_dom.get('total_results'))

    @property
    def page_size(self):
        "Returns the current number of results in the call (max 10)"
        if self.list_dom is not None:
            return int(self.list_dom.get('page_size'))

    @property
    def page_number(self):
        "Returns the current page for the results"
        if self.list_dom is not None:
            return int(self.list_dom.get('page_number'))

    @property
    def total_pages(self):
        "Returns the number of total pages"
        if self.list_dom is not None:
            total_results = self.total_results
            return total_results // 10 + (1 if total_results % 10 else 0)

    @property
    def more_pages(self):
        "Returns if the current page is not the last page"
        if self.list_dom is not None:
            return bool(self.total_pages != self.page_number)


class BookRequest(ISBNdbRequest):
    """BookRequest ISBNdb API
    Handles Books related queries to return Books objects

    The expected information in a BookRequest response is a detail view:

            <?xml version="1.0" encoding="UTF-8"?>
            <ISBNdb server_time="2005-07-29T02:41:22">
                <BookList total_results="1" page_size="10" page_number="1"
                           shown_results="1">
                <BookData book_id="law_and_disorder" isbn="0210406240">
                    <Title>Law and disorder</Title>
                    <TitleLong>
                        Law and disorder: law enforcement in television
                        network news
                    </TitleLong>
                    <AuthorsText>V. M. Mishra</AuthorsText>
                    <PublisherText publisher_id="asia_pub_house">
                        New York: Asia Pub. House, c1979.
                    </PublisherText>
                    <Details dewey_decimal="302.2/3"
                        dewey_decimal_normalized="302.23"
                        lcc_number="PN4888"
                        language="eng"
                        physical_description_text="x, 127 p. ; 22 cm."
                        edition_info=""
                        change_time="2004-10-19T23:52:56"
                        price_time="2005-07-29T02:06:41" />
                    </BookData>
                </BookList>
            </ISBNdb>

    Example of use:

    >>> books = BookRequest('title', 'cryptonomicon').get().books
    >>> (book[0].title, book[0].authors)
    ('Baroque Cycle', 'Books LLC (Creator)')
    """

    FIELDS = ('isbn', 'title', 'combined', 'full', 'book_id', 'person_id',
              'publisher_id', 'subject_id')

    def __init__(self, field, value, page=1):
        "The request filtered by field using value and retrieves the page 1 "
        if field not in self.FIELDS:
            raise ISBNdbRequestError("Unkown field '{0}' for collection "
                                "'books'".format(field))
        super(BookRequest, self).__init__(collection='books', field=field,
                                          value=value, page=page,
                                          trans=self._parse, results='details')

    def get(self):
        "Override default get to fetch Google Book data"
        super(BookRequest, self).get()

        # fetch covers and extra info per book
        data = self.distpach_data([GoogleBooksRequest(book.isbn)
                                   for book in self.books])

        # Append all fetch data to the book as an attribute
        # it will add the field as None if not present
        for i, book in enumerate(self.books):
            for field in GoogleBooksRequest.FIELDS:
                book.__setattr__(field, data[i].get(field))

        return self

    @property
    def books(self):
        return self.data

    @staticmethod
    def _parse(bdata):
        """Parses a book receiving the BoookData element
        Non present or empty data will become None
        Returns an initialized Book object
        """
        bdict = {
            'book_id': bdata.get('book_id'),
            'isbn': bdata.get('isbn'),
            'title': bdata.Title.text,
            'title_long': bdata.TitleLong.text,
            'authors_text': bdata.AuthorsText.text,
            'publisher_id': bdata.PublisherText.get('publisher_id'),
            'publisher': bdata.PublisherText.text,
            'language': bdata.Details.get('language'),
        }

        # Clean the data
        for key in bdict:
            item = bdict.get(key)
            if item is not None:
                # Remove trailing spaces from strings
                item = item.strip()

                # Set empty values to None
                if not item:
                    item = None

            bdict[key] = item

        # Add derived data
        authors_text = bdict['authors_text']
        if authors_text:
            bdict['authors'] = [a for a in authors_text.split(',') if a]

        return Book(**bdict)


class Book(object):
    """Book user class

    All listed fields are garanteed to exist but it can be None

    All the listed fiels are strings or numbers except:
        authors: list of strings
    """

    FIELDS = ('book_id', 'isbn', 'title', 'title_long', 'authors_text',
              'authors', 'publisher_id', 'publisher', 'language', 'extra',
              'subject', 'subject_id')

    def __init__(self, **kwargs):
        for field in self.FIELDS:
            self.__setattr__(field, kwargs.get(field, None))

    def __str__(self):
        return "{title} by: {author}".format(title=self.title,
                                             author=self.authors_text)

    def __repr__(self):
        return "{cls} {str}".format(cls=self.__class__, str=str(self))


class AuthorRequest(ISBNdbRequest):
    """AuthorRequest ISBNdb API
    Handles Author related queries to return person_ids

    The expected information in a BookRequest response is this dom:

            <?xml version="1.0" encoding="UTF-8"?>
            <ISBNdb server_time="2006-01-22T20:51:46">
                <AuthorList total_results="1" page_size="10" page_number="1"
                              shown_results="1">
                    <AuthorData person_id="anthony_a_atkinson">
                         currently represents two searches.
                    <Name>Anthony A. Atkinson</Name>
                    </AuthorData>
                </AuthorList>
            </ISBNdb>

    The result is a list of person_id
    """

    def __init__(self, name, page=1):
        "Gets a list of person_ids by name"
        super(AuthorRequest, self).__init__(collection='authors', field='name',
                                            value=name, page=page, trans=lambda
                                            e: e.get('person_id'))

    @property
    def authors(self):
        return self.data


class PublisherRequest(ISBNdbRequest):
    """AuthorRequest ISBNdb API
    Handles Publisher related queries to return publisher_ids

    The expected information in a PublisherRequest response is this dom:

            <?xml version="1.0" encoding="UTF-8"?>
            <ISBNdb server_time="2006-01-18T12:55:01">
                <PublisherList total_results="2" page_size="10" page_number="1"
                                shown_results="2">
                  <PublisherData publisher_id="dearborn_trade_a_kaplan_profes">
                  <Name>Dearborn Trade, a Kaplan Professional Company </Name>
                  </PublisherData>
                  <PublisherData publisher_id="kaplan">
                     <Name>Kaplan</Name>
                  </PublisherData>
                </PublisherList>
            </ISBNdb>

    The result is a list of publisher_id
    """

    def __init__(self, name, page=1):
        super(PublisherRequest, self).__init__(collection='publisher',
                            field='name', value=name, page=page,
                            trans=lambda e: e.get('publisher_id'))

    @property
    def publishers(self):
        return self.data


class SubjectRequest(ISBNdbRequest):
    """SubjectRequest ISBNdb API
    Handles Subject related queries to return their subject_id

    The expected information in a SubjectRequest response is this dom:

    <?xml version="1.0" encoding="UTF-8"?>
    <ISBNdb server_time="2006-01-13T12:13:14">
        <SubjectList total_results="2" page_size="10" page_number="1"
                shown_results="2">
            <SubjectData subject_id="orthodontics_examinations_questions_etc"
                   book_count="2" marc_field="652" marc_indicator_1=""
                   marc_indicator_2="">
                <Name>Orthodontics -- Examinations, questions, etc</Name>
            </SubjectData>

            <SubjectData subject_id="orthodontics_diagnosis_examinations"
              book_count="3" marc_field="650" marc_indicator_1=""
              marc_indicator_2="0">
                <Name>Orthodontics -- Diagnosis -- Examinations
                , questions, etc
                </Name>
            </SubjectData>
        </SubjectList>
    </ISBNdb>


    The result is a list of subject_id
    """

    def __init__(self, name, page=1):
        super(SubjectRequest, self).__init__(collection='subjects',
                            field='name', value=name, page=page,
                            trans=lambda e: e.get('subject_id'))

    @property
    def categories(self):
        return self.data
