from django import template
register = template.Library()

@register.filter
def is_current_page(url, request):
    # print 'url:', url
    # print 'request:', request.get_full_path(), request.path

    if url == request.get_full_path() or url == request.path:
        return True
    else:
        return False
