# -*- coding: utf-8 -*-
import mypysnmp
import snmp_ifrate
from django.shortcuts import render_to_response, redirect
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core import serializers
import forms
import sys
import json
import calendar
import datetime
from time import sleep

COMMUNITY = 'public'
OIDS = {
    'sysName': '.1.3.6.1.2.1.1.5.0',
    'sysDescr': '.1.3.6.1.2.1.1.1.0',
    'sysUpTime': '.1.3.6.1.2.1.1.3.0',
    'sysDescr': '.1.3.6.1.2.1.1.1.0',
    # if table:
    'ifDescr': '.1.3.6.1.2.1.2.2.1.2',           # full interface name
    'ifName': '.1.3.6.1.2.1.31.1.1.1.1',         # interface name
    'ifAlias': '.1.3.6.1.2.1.31.1.1.1.18',       # interface description
    'ifSpeed': '.1.3.6.1.2.1.2.2.1.5',           # maximum speed of interface
    'ifHighSpeed': '.1.3.6.1.2.1.31.1.1.1.15',   # maximum speed of interface in megabytes
    'ifAdminStatus': '.1.3.6.1.2.1.2.2.1.7',
    'ifOperStatus': '.1.3.6.1.2.1.2.2.1.8',
    # if counters:
    'ifInOctets': '.1.3.6.1.2.1.2.2.1.10',
    'ifHCInOctets': '.1.3.6.1.2.1.31.1.1.1.6',   # 64 bit counter
    'ifOutOctets': '.1.3.6.1.2.1.2.2.1.16',     
    'ifHCOutOctets': '.1.3.6.1.2.1.31.1.1.1.10', # 64 bit counter
    'ifInErrors': '.1.3.6.1.2.1.2.2.1.14',
    'ifOutErrors': '.1.3.6.1.2.1.2.2.1.20',
    }

#online_count = {}

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def ifrate_page(request):
    '''main ifrate page
    '''
    def js_timestamp_from_datetime(dt):
        return calendar.timegm(dt.timetuple()) * 1000

    errors = []
    warnings = []

    if request.is_ajax() and request.method == 'GET':
        # ajax requests from poller
        #
        format = 'json' # output format switcher. you can use this parameter as fucntion parameter.
        if format == 'xml':
            mimetype = 'application/xml'
        if format == 'json':
            mimetype = 'application/javascript'

        host = request.GET['host']
        community = request.GET['community']
        snmpver = request.GET['snmpver']
        if_id = request.GET['if_id']
        upd_int = int(request.GET['upd_int'])
        # защита от самых умных
        if upd_int < 5:
          upd_int = 5
        elif upd_int > 3600:
          upd_int = 3600

        # online counter
        # may throw error while trying to change online_count simultaniosly
        # try:
        #     ip = get_client_ip(request)
        #     hosts = {}
        #     if ip in online_count:
        #         hosts = online_count[ip]
        #     hosts[host] = {'ts': datetime.datetime.now(), 'upd_int': upd_int}
        #     online_count[ip] = hosts
        # except RuntimeError: # dict size changed
        #     pass

        err_flag = True
        # важно чтобы этот паролик не попал в код страницы
        if not community:
            community = COMMUNITY
        try:
            poller = snmp_ifrate.SnmpIfInfo(address=host, community=community, snmpver=snmpver)
            rate = poller.get_ifrate_forced(if_id=if_id, req_delay=upd_int)
            #rate = poller.get_ifrate_forced(if_id=if_id, req_delay=upd_int, force64bit=use64bit)
            err_flag = False
        except mypysnmp.SnmpError as ei:
            errors.append(ei)
        except snmp_ifrate.MyError as ei:
            errors.append(ei)
        except:
            errors.append(u'Ошибка получения данных: {0}'.format(sys.exc_info()[1]))
        
        if err_flag:
            # return AjaxError
            errors.insert(0, u'Не могу подключиться к {0}!'.format(host))
            out = ''
            for i in errors:
                out += unicode(i) + u' '
            sleep(upd_int)
            return HttpResponse(out)
        else:
            jscript_data = rate
            jscript_data['timestamp'] = js_timestamp_from_datetime(datetime.datetime.utcnow())

            # DEBUG only: random error generator
            # import random, time
            # rnd = int(random.random() * 10)
            # if rnd > 6:
            #     jscript_data['in_errors'] = int(time.time())
            # if rnd > 8:
            #     jscript_data['out_errors'] = int(time.time())

            jscript_data = json.dumps(jscript_data)
            return HttpResponse(jscript_data, mimetype)

    if 'host' in request.GET:
        # заданы параметры хоста, но не задан интерфейс
        form_host_query = forms.HostQueryForm(request.GET)
        if form_host_query.is_valid():
            if 'interface' in request.GET:
                # заданы параметры хоста и выбран интерфейс
                # сначала собираем общие данные об интерфейсе

                ifdata = {}
                
                host = form_host_query.cleaned_data['host']
                community = form_host_query.cleaned_data['community']
                snmpver = form_host_query.cleaned_data['snmpver']
                if_id = form_host_query.data['interface']

                ifdata['host'] = host
                ifdata['community'] = community
                ifdata['snmpver'] = snmpver
                ifdata['if_id'] = if_id
                ifdata['ajax_url'] = reverse('ifrate')  # url of ajax request handler
                
                # важно чтобы этот паролик не попал в код страницы
                if not community:
                    community = COMMUNITY
                try:
                    # collect initial interface data:
                    poller = snmp_ifrate.SnmpIfInfo(host, community, snmpver)
                    ifdata['sysname'] = poller.get_sysname()
                    speed, units = poller._convert_speed(poller.get_ifmaxspeed(if_id=if_id))
                    ifdata['ifmaxspeed'] = "{0} {1}bit/s".format(str(speed), units)
                    rs = mypysnmp.snmpget(host, OIDS['ifDescr'] + '.' + if_id, community, snmpver)
                    ifdata['if_descr'] = rs['value']
                    rs = mypysnmp.snmpget(host, OIDS['ifAlias'] + '.' + if_id, community, snmpver)
                    ifdata['if_alias'] = rs['value'] if rs['value'] else ''
                    rs = mypysnmp.snmpget(host, OIDS['ifName'] + '.' + if_id, community, snmpver)
                    ifdata['if_name'] = rs['value']
                    
                    try:
                        rs = mypysnmp.snmpget(host, (OIDS['ifAdminStatus'] + '.' + if_id, 
                                OIDS['ifOperStatus'] + '.' + if_id), community, snmpver, exception=True)
                    except mypysnmp.SnmpError:
                        ifdata['if_admst'] = None
                        ifdata['if_opst'] = None
                    else:
                        #if not rs['errorIndication']:
                        ifdata['if_admst'] = rs['value'][0]
                        ifdata['if_opst'] = rs['value'][1]
                        if not '1' in ifdata['if_admst'] or not '1' in ifdata['if_opst']:
                            warnings.append(u'Внимание: интерфейс выключен администратором (ifAdminStatus: {0}).'.format(ifdata['if_admst']))
                            warnings.append(u'Внимание: нет линка (ifOperStatus: {0})'.format(ifdata['if_opst']))
                    
                    poller.if_id = if_id
                    poller.if_name = if_id
                    ifdata['if_maxspd'] = poller.get_ifmaxspeed()
                    speed, units = poller._convert_speed(ifdata['if_maxspd'])
                    ifdata['if_maxspd_str'] = '{0} {1}'.format(speed, units)
                    
                    # rs = mypysnmp.snmpget(host, OIDS['ifInErrors'] + '.' + if_id, community, snmpver)
                    # if rs['value']:
                    #     poller.ifinerrors = int(rs['value'])
                    # else:
                    #     poller.ifinerrors = '?'
                    # rs = mypysnmp.snmpget(host, OIDS['ifOutErrors'] + '.' + if_id, community, snmpver, exception=True)
                    # if rs['value']:
                    #     poller.ifouterrors = int(rs['value'])
                    # else:
                    #     poller.ifouterrors = '?'
                    # ifdata['if_in_errors'] = poller.ifinerrors
                    # ifdata['if_out_errors'] = poller.ifouterrors
                    # if ifdata['if_in_errors'] > 0: warnings.append(u'Внимание: ненулевой счетчик ошибок на входе интерфейса: {0}.'.format(ifdata['if_in_errors']))
                    # if ifdata['if_out_errors'] > 0: warnings.append(u'Внимание: ненулевой счетчик ошибок на выходе интерфейса: {0}.'.format(ifdata['if_out_errors']))
                except mypysnmp.SnmpError as ei:
                    errors.append(ei)
                except snmp_ifrate.MyError as ei:
                    errors.append(ei)
                except ValueError as ei:
                    errors.append('Получены данные неизвестного формата: {}'.format(ei))
            else:
                host = form_host_query.cleaned_data['host']
                community = form_host_query.cleaned_data['community']
                snmpver = form_host_query.cleaned_data['snmpver']
                err_flag = True
                if not community:
                    community = COMMUNITY
                try:
                    poller = snmp_ifrate.SnmpIfInfo(host, community, snmpver)
                    poller.get_ifnametable()
                    err_flag = False
                except mypysnmp.SnmpError as ei:
                    errors.append(ei)
                except snmp_ifrate.MyError as ei:
                    errors.append(ei)
                except:
                    errors.append(u'Ошибка при получении информации об интерфейсах: {0}'.format(sys.exc_info()[1]))
                if err_flag:
                    errors.insert(0, u'Не могу подключиться к {0}!'.format(host))
                else:
                    interfaces = [i for i in sorted(poller.ifnametable, key=poller._sort_natural)]
                    choices = []
                    for i in interfaces:
                        choices.append([poller.ifnametable[i], i])
                    form_host_query = forms.HostQueryForm(request.GET, mychoices=choices)
        else:
            error = u'Правильно задайте имя (или адрес) устройства, строку community и версию протокола SNMP'
    else:
        # начальная страничка с формой:
        # counter
        # now = datetime.datetime.now()
        # ip_list = {}
        # for ip, v in online_count.items():
        #     for host, data in online_count[ip].items():
        #         if now > (data['ts'] + datetime.timedelta(seconds=2*data['upd_int'])):
        #             del online_count[ip][host]
        #         else:
        #             ip_list[ip] = [key for key, val in online_count[ip].items()]

        form_host_query = forms.HostQueryForm(None)
    
    return render_to_response('ifrate.html', locals(), context_instance=RequestContext(request))
