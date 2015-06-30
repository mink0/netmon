# Create your views here.
# -*- coding: utf-8 -*-
import mypysnmp
import snmp_getmacs
from django.shortcuts import render_to_response, redirect
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.template import RequestContext
from django.core.urlresolvers import reverse
import forms
import operator # for smart sorting
import sys

COMMUNITY = 'public'

class MyError(Exception):
    '''base class for all exceptions raised by this module
    '''
    def __str__(self):
        return '{0}.{1}: {2}'.format(__name__, self.__class__.__name__, self.args[0])

def html_table(table, header=[]):
    '''Make HTML table body from: ((header),(row1),(row2)...) (without table tag)
    '''
    try:
        html = ur''
        if header:
            html += '<thead>\n'
            html += u'<tr>'
            for i in header:
                html += ur'<th>{0}</th>'.format(i)
            html += ur'</tr>'
            html += '\n</thead>'
        
        html += '\n<tbody>'
        for row in table:
            html += u'\n<tr>'
            for item in row:
                html += ur'<td>{0}</td>'.format(item)
            html += ur'</tr>'
        html += '\n</tbody>'
    except IndexError:
        html += 'Error! html_table: wrong data!'
    return html

def getmacs_page(request):
    '''main getmacs page
    '''
    errors = []
    warnings = []
    if 'host' in request.GET:
        form_host_query = forms.HostGwQueryForm(request.GET)
        if form_host_query.is_valid():
            # заданы все параметры хоста
            address = form_host_query.cleaned_data['host']
            community = form_host_query.cleaned_data['community']
            snmpver = form_host_query.cleaned_data['snmpver']
            gwaddress = form_host_query.cleaned_data['gw']
            collect_vlans = False
            verbose = False
            cdptable = None
            if not community:
                community = COMMUNITY
            err_flag = True
            try:
                if verbose: print('* Trying the host {0}...'.format(address))
                device = snmp_getmacs.SnmpDevInfo(address, community, snmpver)
                device.get_sysdescr()
                if 'Cisco' in device.sysdescr:
                    collect_vlans = True
                if verbose: print(device.sysdescr)
                #rows, columns = snmp_getmacs.terminal_size()
                device.get_sysname()
                #print(device.sysname.center(columns))
                #print(device.sysdescr.splitlines()[0][:columns].center(columns))

                if verbose: print('* Getting interface table...')
                iftable = device.get_iftable()
                if verbose:
                    print('-' * columns)
                    for i in iftable: print(i)
                    print('-' * columns)

                if verbose: print('* Getting MAC address table...')
                if collect_vlans:
                    mactable = device.get_mactable(vlans=device.get_vlans_cisco())
                    cdptable = device.get_cdp_nbs()
                else:
                    mactable = device.get_mactable()
                for i in device.log_pop():  # print errors and warnings
                    warnings.append(i)
                if verbose:
                    print('-' * columns)
                    for i in mactable: print(i)
                    print('-' * columns)

                if verbose: print('* Getting ARP address table from {0}...'\
                                    .format(gwaddress if gwaddress else address))
                if gwaddress:
                    arptable = device.get_arptable(address=gwaddress)
                else:
                    arptable = device.get_arptable()
                for i in device.log_pop():  # print errors and warnings
                    warnings.append(i)
                if verbose:
                    print('-' * columns)
                    for i in arptable: print(i)
                    print('-' * columns)

                if verbose: print("* It's done! Forming output table...")
                # forming output table:
                if collect_vlans:
                    table_header = ['#', 'id', u'Интерфейс', u'Описание', 'Vlan', 'MAC', 'IP']
                else:
                    table_header = ['#', 'id', u'Интерфейс', u'Описание', 'MAC', 'IP']

                table = []
                active_ports = {}
                for macitem in mactable:
                    if not macitem['ifid']: continue    # Port SNMP ID != None

                    active_ports[macitem['ifid']] = True
                    try:
                        id = int(macitem['ifid'])   # for accurate sorting
                    except:
                        id = macitem['ifid']


                    ifname = ''
                    descr = ''
                    alias = ''
                    vlan = ''
                    for j in iftable:
                        #print j.ifid, macitem['ifid']
                        if j['ifid'] == macitem['ifid']:
                            ifname = j['ifname']
                            descr = j['ifdescr']
                            alias = j['ifalias']
                            #vlan = macitem['vlan']
                    ip = ''
                    for j in arptable:
                        if str(j['mac']).lower() == str(macitem['mac']).lower():    # case insensitive
                            ip = j['ipaddr']
                            break

                    if collect_vlans:
                        table.append([id, ifname, alias, macitem['vlan'], macitem['mac'], ip])
                    else:
                        table.append([id, ifname,  alias, macitem['mac'], ip])

                # sorting by ID
                table = sorted(table, key=operator.itemgetter(0))
                if not table:
                    raise MyError('No data! SNMP-mib not supported for this device')
                for i in xrange(len(table)):
                    if table[i][0] != '':
                        table[i][0] = '.' + str(table[i][0])
                    table[i].insert(0, i + 1) # insert index

                result_table = html_table(table, table_header)
                # thead1 = '<tr><th class="topheader" colspan="{0}">'.format(len(table_header)) + device.sysname + '</th></tr>'
                thead1 = ''
                result_table = '<thead>\n' + thead1 + result_table[(len('<thead>\n') - 1):]
                err_flag = False

                down_table = []
                down_header = ['#', 'id', u'Интерфейс', u'Описание', u'Подключение', u'Линк']
                for item in iftable:
                    if item['ifid'] not in active_ports:
                        if_adm = u'вкл.' if item['ifadm'] == '1' else u'порт выключен'
                        if_oper = u'есть' if item['ifoper'] == '1' else u'нет линка'
                        down_table.append([item['ifid'], item['ifname'], item['ifalias'], if_adm, if_oper])

                for i in xrange(len(table)):
                    if table[i][0] != '':
                        table[i][0] = '.' + str(table[i][0])
                    table[i].insert(0, i + 1)   # insert index

                # sorting by if_oper
                down_table = sorted(down_table, key=operator.itemgetter(3)) # сортируем по if_oper
                for i in xrange(len(down_table)):
                    if down_table[i][0] != '':
                        down_table[i][0] = '.' + str(down_table[i][0])
                    down_table[i].insert(0, i + 1)  # insert index

                result_down_table = html_table(down_table, down_header)

                if cdptable:
                    cdp_table_header = ['#', 'id', u'Интерфейс', u'Устройство', u'Тип устройства', u'Подключен к порту']
                    cdp_table = []
                    i = 0
                    for row in cdptable:
                        i += 1
                        cdp_table.append([i, '.' + row['ifid'], row['ifname'], row['dev'], row['type'], row['rport']])

                    result_cdp_table = html_table(cdp_table, cdp_table_header)


            except mypysnmp.SnmpError as ei:
                errors.append(ei)
            except snmp_getmacs.MyError as ei:
                errors.append(ei)
            except MyError as ei:
                errors.append(ei)
            # except:
            #     errors.append(u'Ошибка при получении информации об интерфейсах: {0}'.format(sys.exc_info()[1]))
            if err_flag:
                errors.insert(0, u'Не могу подключиться к {0}!'.format(address))

            
        else:
            error = u'Правильно задайте имя (или адрес) устройства, строку community и номер протокола SNMP'
                
    else:
        # рисуем форму для ввода параметров
        form_host_query = forms.HostGwQueryForm(None)
                
    return render_to_response('getmacs.html', locals(), context_instance=RequestContext(request)) 
