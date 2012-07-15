#from werkzeug.utils import redirect
#from werkzeug.wsgi import SharedDataMiddleware
#from werkzeug.wrappers import Request, Response

import os
import json

from search import Search, SearchError

from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import  SharedDataMiddleware
from werkzeug.exceptions import HTTPException
from werkzeug.routing import Map, Rule, Submount

from jinja2 import Environment, FileSystemLoader


class BookSearch(object):
    """
        Application for Book searching

        urls:
            ('/', endpoint='index')
            ('/b/<by>/<query>', endpoint='search/<by>/<query>')
            ('/b/<slug>', endpoint='get_book/<slug')

        """

    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path),
                                     autoescape=True)
        self.url_map = Map([
            Rule('/', endpoint='index'),
            Submount('/b', [
                Rule('/<string:by>/<string:query>/<int:page>', endpoint='search'),
                Rule('/<string:by>/<string:query>', endpoint='search'),
                Rule('/<string:slug>', endpoint='get_book')
            ])
        ])

    def on_index(self, request):
        return self.render('index.html')

    def on_get_book(self, request, slug):
        """
        Answers with a JSON version of the search
        Searches by book_id
        """
        return self.on_search(request, by='book_id', query=slug)

    def on_search(self, request, by, query, page=1):
        """
        Answers with a JSON version of the search
        The search uses a field to search (by) and the value (query)
        Arguments: by, query
        """
        #mimetype = 'application/json'

        try:
            s = Search(by=by, query=query, page=page).get()
        except SearchError, err:
            s = {'error': err}

        # Make the Book class json-serializable
        #if s.books is not None:
        #    s.books = [b.__dict__ for b in s.books]

        return self.render('result.html', s=s)
        #return Response(json.dumps(s.__dict__), mimetype=mimetype)

    #### WSGI stuff
    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)
        except HTTPException, e:
            return e

    def render(self, template_name, **context):
        "Renders the given template and returns a Response"
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def wsgi_app(self, environ, start_response):
        "Basics to respond to HTTP requests"
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        "Make the object callable for WSGI"
        return self.wsgi_app(environ, start_response)


def create_app():
    app = BookSearch()
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
        '/static': os.path.join(os.path.dirname(__file__), 'static')
    })
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', 5000, create_app(),
               use_debugger=True, use_reloader=True)
