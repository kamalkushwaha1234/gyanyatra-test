import logging
from django.shortcuts import render
logger = logging.getLogger('django')

def handler404(request, exception):
    response = render(request, '404.html', {})
    response.status_code = 404
    return response

def handler500(request):
    response = render(request, '500.html', {})
    response.status_code = 500
    return response