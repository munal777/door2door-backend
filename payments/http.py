from django.http import HttpResponsePermanentRedirect

class HttpResponsePermanentRedirect(HttpResponsePermanentRedirect):
    allowed_schemes = ['https', 'http', 'mobileapp']