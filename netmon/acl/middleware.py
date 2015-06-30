# -*- coding: utf-8 -*-
from datetime import datetime
from netmon.acl.models import IPAccess
from django.shortcuts import render_to_response
import pytz

#
# Проверяются только новые сессии
# last_login - время открытия последней сессии
#
class IPAccessMiddleware(object):
    def process_request(self, request):
        client_ip = get_client_ip(request)
        if not (client_ip == '127.0.0.1' or request.session.get('ip_has_checked', False)):
            try:
                user = IPAccess.objects.get(ip=client_ip)
                request.session['ip_has_checked'] = True
                if user.last_login is not None:
                    delta = datetime.utcnow().replace(tzinfo=pytz.utc) - user.last_login
                if user.last_login is None or delta.total_seconds() > 60:
                    user.last_login = datetime.utcnow().replace(tzinfo=pytz.utc)
                    user.save()
            except IPAccess.DoesNotExist:
                # return HttpResponse('Unauthorized!', status=401)
                return render_to_response('403.html', locals(), status=401)
        return None


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
