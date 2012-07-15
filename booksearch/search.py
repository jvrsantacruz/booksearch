# -*- coding: utf-8 -*-
"""
Book search
"""

from collections import OrderedDict

from api import BookRequest
from api import AuthorRequest
from api import APIRequestError
from api import SubjectRequest
from api import PublisherRequest


class SearchError(Exception):
    "Search Exception class"
    pass


class Search(object):
    """Implements the search book functionality
    Allows to perform a Book search by using the following filters:
       ('isbn', 'title', 'author', 'publisher', 'subject')

    The filters 'author', 'publisher' and 'subject' requires more
     than one API call and currently represents two searches.
    """

    FILTERS = ('isbn', 'title', 'author', 'publisher', 'subject', 'book_id')

    def __init__(self, by, query, page=1):
        if by not in self.FILTERS:
            raise SearchError("Invalid filter '{0}'".format(by))

        self.by = by
        self.query = query
        self.page = page
        self.books = None
        self.results = None
        self.total_pages = None
        self.total_results = None

    def get(self):
        "Searches for the books"
        if self.books is None:
            method = '_get_by_' + self.by
            try:
                self.books = self.__getattribute__(method)()
            except APIRequestError, err:
                raise SearchError(err)

        self.results = len(self.books)

        return self

    def _get_by_isbn(self):
        return self._get_direct(self.by)

    def _get_by_title(self):
        return self._get_direct(self.by)

    def _get_by_book_id(self):
        return self._get_direct(self.by)

    def _get_by_author(self):
        """Searchs for the author and then for the books by author_id

        Only 3 books from each author is listed.
        """
        return self._2level_search(AuthorRequest, 'person_id')

    def _get_by_publisher(self):
        """Searchs for the publisher and then for the books by publisher_id

        Only 3 books from each publisher is listed.
        """
        return self._2level_search(PublisherRequest, 'publisher_id')

    def _get_by_subject(self):
        """Searchs for the subject and then for the books by subject_id

        Only 3 books from each subject is listed.
        """
        return self._2level_search(SubjectRequest, 'subject_id')

    def _get_direct(self, field):
        "Get a list of books searching directly on the server"
        req = BookRequest(field=field, value=self.query, page=self.page).get()
        self.total_pages = req.total_pages
        self.total_results = req.total_results
        return req.books

    def _2level_search(self, firstreq, bookfield):
        """Multiple searchs (by author, publisher, subject)
        needs to search for the author/publisher/subject first
        and then return the results.

        The pagination then it's not straightforward and just
        3 books per each first level subject is displayed.
        """
        self.page = (self.page - 1) / 3 + 1  # fake pagination
        req = firstreq(name=self.query, page=self.page).get()
        self.total_pages = req.total_pages * 3
        self.total_results = req.total_results * 3

        # Get the 3 first books for the 3 first authors in the search
        requests = [BookRequest(field=bookfield, value=data_id)
                    for data_id in req.data[:3 * self.page]]
        BookRequest.distpach(requests)

        books = OrderedDict()  # remove duplicates maintaining order
        for r in requests:
            if r.data is not None:
                books.update({d: None for d in r.data[:3]})

        return list(books.keys())
