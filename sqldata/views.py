# Create your views here.
# -*- coding: utf-8 -*-
import sys
import datetime
import calendar
from django.utils import timezone
import json
import operator
from django.shortcuts import render_to_response, redirect
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.template import RequestContext
from models import Device, Interface, Poll, Iftraffic, Sysuptime
from forms import InterfaceTimeForm
from django.core.urlresolvers import reverse
from django.conf import settings
import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor

DTF = settings.MYDATETIME_FORMAT

def html_table_from_model(django_model, rows_to_render=None, pk_key=None, url_prefix='/',
                                                start_item=None, items_per_page=None):
    '''Simple django model HTML table renderer
    Connects to SQL table and return HTML table with its data
    '''
    errors = []
    try:
        table_full = django_model.objects.all()
    except:
        errors.append(u'Ошибка! Не могу связаться с базой данных.')
        table_full = []
    try:
        #table_full_head = vars(table_full[0]) # python native style - buggy for django models!
        table_full_head = [i.name for i in table_full[0]._meta.fields]
    except IndexError:
        errors.append(u'Ошибка! Нет данных в базе <b>{0}</b>.'.format(django_model))
        table_full_head = []
    except:
        errors.append(u'Неизвестная ошибка! Не могу получить заголовок таблицы <b>{0}</b>.'.format(django_model))
    if errors:
        return '', errors

    if rows_to_render is not None:
        table_full_head = [i for i in rows_to_render]


    table_full_html = '<thead>\n'
    table_full_html += '<tr>'
    for i in table_full_head:
        table_full_html += '<th>{0}</th>'.format(i)
    table_full_html += '</tr>'
    table_full_html += '\n</thead>'

    table_full_html += '\n<tbody>\n'
    for row in table_full:
        table_full_html += '<tr>'
        for i in table_full_head:
            #item = vars(row)[i]    # python native style:
            item = getattr(row, i)  # django style
            if pk_key is not None:
                table_full_html += '<td><a href="{1}">{0}</a></td>'.format(item,
                                                            url_prefix + str(getattr(row, pk_key)) + '/')
            else:
                table_full_html += '<td>{0}</td>'.format(item)

        table_full_html += '</tr>'
    table_full_html += '</tbody>\n'
    return table_full_html, ''


def main_page(request):
    ''' site index page
    '''
    errors = []
    warnings = []
    print 'User is :', request.user
    print 'User auth is :', request.user.is_authenticated()
    # def get_client_ip(request):
    #     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    #     if x_forwarded_for:
    #         ip = x_forwarded_for.split(',')[0]
    #     else:
    #         ip = request.META.get('REMOTE_ADDR')
    #     return ip


    # FIXME: add column localization
    class DeviceTable(tables.Table):
        id = tables.LinkColumn('device/id', args=[A('id')])
        name = tables.LinkColumn('device/id', args=[A('id')])
        ip_mgmt = tables.LinkColumn('device/id', args=[A('id')])
        sys_object_id = tables.LinkColumn('device/id', args=[A('id')])
        first_poll = tables.LinkColumn('device/id', args=[A('id')])
        last_poll = tables.LinkColumn('device/id', args=[A('id')])

        class Meta:
            model = Device
            attrs = {'class': 'sortable'}
            fields = ('id', 'name', 'ip_mgmt', 'sys_object_id', 'first_poll', 'last_poll')

    class DeviceEolTable(DeviceTable):
        id = tables.LinkColumn('device/id', args=[A('id')])
        name = tables.LinkColumn('device/id', args=[A('id')])
        ip_mgmt = tables.LinkColumn('device/id', args=[A('id')])
        sys_object_id = tables.LinkColumn('device/id', args=[A('id')])
        first_poll = tables.LinkColumn('device/id', args=[A('id')])
        last_poll = tables.LinkColumn('device/id', args=[A('id')])
        # eol = tables.LinkColumn('device/id', args=[A('id')])

        class Meta:
            model = Device
            attrs = {'class': 'sortable'}
            fields = ('id', 'name', 'ip_mgmt', 'sys_object_id', 'first_poll', 'last_poll', 'eol')


    try:
        dev_list = Device.objects.all()
        polls = Poll.objects.all()
        sysuptimes = Sysuptime.objects.all()
    except:
        error = u'Ошибка при попытке связаться с базой данных!'
        return render_to_response('index.html', locals(), context_instance=RequestContext(request))

    dev_table = []
    dev_eol_table = []
    dev_count = 0
    dev_eol_count = 0
    for device in dev_list:
        try:
            first_uptime = sysuptimes.filter(dev_id=device.id).order_by('poll_id')[0]
            last_uptime = sysuptimes.filter(dev_id=device.id).order_by('-poll_id')[0]
            # FIXME
            # приходится переводить в локальное время в view, правильно было бы делать это в template
            # {{ value|localtime }}
            device.first_poll = timezone.localtime(polls.get(id=first_uptime.poll_id).dt).strftime(DTF)
            device.last_poll = timezone.localtime(polls.get(id=last_uptime.poll_id).dt).strftime(DTF)
        except:
            warnings.append(u'Недостаточно данных для {}. Подождите сбора статистики...'.format(device))
            #warnings.append(u'Не могу собрать данные для {0}: {1}'.format(device, 'first_poll, last_poll'))
            #print '> Error: {}'.format(sys.exc_info())

        if not device.eol:
            dev_count += 1
            dev_table.append(device)
        else:
            dev_eol_count += 1
            dev_eol_table.append(device)

    dev_table = DeviceTable(dev_table)
    tables.RequestConfig(request, paginate=False).configure(dev_table)         # делаем рабочими pagination, sorting и ...
    dev_eol_table = DeviceEolTable(dev_eol_table)
    tables.RequestConfig(request, paginate=False).configure(dev_eol_table)     # делаем рабочими pagination, sorting и ...
    return render_to_response('index.html', locals(), context_instance=RequestContext(request))

def device_page(request, device_str):
    ''' Interface list from specified device
    '''
    errors = []
    warnings = []

    class InterfaceTable(tables.Table):
        id = tables.LinkColumn('interface/id', args=[A('id')])
        if_description = tables.LinkColumn('interface/id', args=[A('id')])
        if_index = tables.LinkColumn('interface/id', args=[A('id')])
        if_alias= tables.LinkColumn('interface/id', args=[A('id')])
        if_max_speed = tables.LinkColumn('interface/id', args=[A('id')])
        enable_collect = tables.LinkColumn('interface/id', args=[A('id')])
        class Meta:
            model = Interface
            attrs = {'class': 'sortable'}
            fields = ('id', 'dev_id', 'if_description', 'if_index', 'if_alias', 'if_max_speed', 'enable_collect')

    # find our device:
    device = None
    try:
        dev_id = int(device_str)
        device = Device.objects.get(id=dev_id)
    except ValueError:  # if device_str not int!
        pass
    except Device.DoesNotExist, e:
        errors.append(u'Не могу найти указанное устройство в SQL базе: id = {0}.<p>{1}</p>'.format(dev_id, e))
    if device is None:
        try:
            devices = Device.objects.filter(name__iexact=device_str)
            device = devices[0] # choose first
        except Device.DoesNotExist, e:
            errors.append(u'Не могу найти указанное устройство в SQL базе: name = {0}.<p>{1}</p>'
                                                                .format(device_str, e))
        except:
            pass

    if device is None:
        raise Http404
        # return render_to_response('device.html', locals(), context_instance=RequestContext(request))

    dev_id = device.id
    try:
        if_list = Interface.objects.filter(dev_id__exact=dev_id)
    except Interface.DoesNotExist, e:
        errors.append(u'Не могу найти интерфейсы для {0} в SQL базе.<p>{1}</p>'.format(device, e))
        return render_to_response('device.html', locals(), context_instance=RequestContext(request))

    interface_table = InterfaceTable(if_list)
    tables.RequestConfig(request, paginate=False).configure(interface_table)     # делаем рабочими pagination, sorting и ...
    return render_to_response('device.html', locals(), context_instance=RequestContext(request))

def interface_main_page(request):
    ''' main Interface page to find a link to the wanted interface
    '''
    # Экспериментальный вид, тестирование возможностей django_tables2
    # Нужна pagination и возможность оформлять model в html в template, что правильнее, чем делать это в view.
    # При этом утрачивается читаемость программы и усложняется отладка и развертывание сервера djnago.
    # Лучше всего дождаться реализации этого функционала в самой django и уж тогда переписать весь свой код.

    INTERFACE_MAIN_TABLE = ('id', 'dev_id', 'if_description', 'if_index', 'if_max_speed', 'enable_collect') # to hide communty string

    # в этом классе назначаем все свойства нашей таблицы. см. django_tables2 API.
    # tables.py
    class IfTable(tables.Table):
        dev_id = tables.LinkColumn('device/id', args=[A('dev_id_id')])
        id = tables.LinkColumn('interface/id', args=[A('id')])
        class Meta:
            model = Interface
            fields = INTERFACE_MAIN_TABLE
            attrs = {'class': 'tight striped sortable'}
            # orderable = False


    # инициализируем таблицу данными. см. django_tables2 API.
    ttable = IfTable(Interface.objects.all())

    # делаем рабочими pagination, sorting и ...
    tables.RequestConfig(request, paginate={"per_page": 400}).configure(ttable)

    # моя функция рендера таблицы из django модели. работает без django_tables2
    # пока оставляю, если вдруг будут проблемы в django_tables2
    # INTERFACE_URL_PREFIX = reverse('interface')
    # if_full_html, errors = html_table_from_model(Interface, rows_to_render=INTERFACE_MAIN_TABLE,
                                                    #pk_key='id', url_prefix=INTERFACE_URL_PREFIX)
    return render_to_response('interface_main.html', locals(), context_instance=RequestContext(request))

def interface_page(request, interface_str, time_begin=None, time_end=None):
    ''' Interface page: to open specified interface graphs and stats
    '''
    errors = []
    warnings = []

    def js_timestamp_from_datetime(dt):
        return calendar.timegm(dt.timetuple()) * 1000
        #return 1000 * time.mktime(dt.timetuple())

    def speed_convert(inspeed):
        ''' simple speed units converter
        '''
        units = ''
        if inspeed > 1e15:
            inspeed = inspeed/1e15
            units = 'P'
        elif inspeed > 1e12:
            inspeed = inspeed/1e12
            units = 'T'
        elif inspeed > 1e9:
            inspeed = inspeed/1e9
            units = 'G'
        elif inspeed > 1e6:
            inspeed = inspeed/1e6
            units = 'M'
        else:
            inspeed = inspeed/1e3
            units = 'k'
        return inspeed, units + r'bit/s'

    def iftraffic_jscalc(iftraffic, polls, sysuptime, interface):
        ''' all statistic calculated here /interface needed
        '''
        if interface.if_counter_capacity == 64: maxcount = 2**64 - 1     # for counter zeroing
        else: maxcount = 2**32 - 1

        out_table = []

        nodata = False  # we have a poll, but dont have iftraffic or sysuptime data
        first = True    # first right element in data, second one is needed to calc a point
        i = 0   # iftraffic and sysuptime index
        #upd_interval_old = 24*60*60
        #p = 0  # polls index
        for p in xrange(len(polls)):
            # data check:
            if sysuptime is None:
                if polls[p].id != iftraffic[i].poll_id:
                    nodata = True
            elif polls[p].id != iftraffic[i].poll_id or polls[p].id != sysuptime[i].poll_id:
                #warnings.append(u'Нет данных для: {0}'.format(polls[p]))
                nodata = True

            if nodata is False:
                in_new = iftraffic[i].val_in
                out_new = iftraffic[i].val_out
                if sysuptime is None:
                    timer_new = polls[p].dt
                else:
                    timer_new = sysuptime[i].uptime

                if not first:
                    if sysuptime is None:
                        upd_interval = timer_new - timer_old
                        upd_interval = upd_interval.seconds
                    else:
                        upd_interval = (timer_new - timer_old)/100.

                    # device reboot check:
                    if upd_interval < 0 and sysuptime is not None:
                        upd_interval = (polls[p].dt - polls[p-1].dt).seconds
                        # Циска сбрасывает snmp счеткики при перезагрузке, поэтому:
                        in_old = 0
                        out_old = 0
                        if sysuptime[i].uptime/100. <= upd_interval:
                            warnings.append(u'Перезагрузка устройства в интервале между <b>{0}</b> и <b>{1}</b>.'
                                .format(timezone.localtime(polls[p-1].dt).strftime(DTF), timezone.localtime(polls[p].dt).strftime(DTF)))

                    if upd_interval <= 0:
                        first = True
                        warnings.append(u'Пропускаю данные: {0} (проверка интервала времени: upd_interval = {1}).'
                                                                        .format(iftraffic[i], upd_interval))
                    else:
                        in_speed = 8. * (in_new - in_old) / upd_interval    # from octets to bits per second
                        out_speed = 8. * (out_new - out_old) / upd_interval
                        # counter zeroing
                        if in_speed < 0:
                            in_speed = 8. * (in_new + maxcount - in_old) / upd_interval
                            #warnings.append(u'Переполнение счетика входящего трафика между {0} и {1}.'.format(timezone.localtime(polls[p-1].dt).strftime(DTF), timezone.localtime(polls[p].dt).strftime(DTF)))
                        if out_speed < 0:
                            out_speed = 8. * (out_new + maxcount - out_old) / upd_interval
                            #warnings.append(u'Переполнение счетика выходящего трафика между {0} и {1}.'.format(timezone.localtime(polls[p-1].dt).strftime(DTF), timezone.localtime(polls[p].dt).strftime(DTF)))

                        # server shutdown check
                        if ('upd_interval_old' in locals() and
                            upd_interval > 0.99 * upd_interval_old
                                and upd_interval < 1.01 * upd_interval_old):
                                    upd_interval_stable = upd_interval

                        if 'upd_interval_stable' in locals() and upd_interval > 2 * upd_interval_old:
                            # insert nodata gap in flot
                            out_table.append([js_timestamp_from_datetime(timezone.localtime(polls[p-1].dt)), None, None])
                            # if no need to convert to localtime and it will be converted on the client side:
                            # out_table.append([js_timestamp_from_datetime(polls[p-1].dt), None, None])
                            warnings.append(u'Нет данных в интервале между <b>{0}</b> и <b>{1}</b>.'
                                .format(timezone.localtime(polls[p-1].dt).strftime(DTF), timezone.localtime(polls[p].dt).strftime(DTF)))

                        upd_interval_old = upd_interval
                        # if no need to convert to localtime and it will be converted on the client side:
                        out_table.append([js_timestamp_from_datetime(timezone.localtime(polls[p].dt)), int(in_speed), int(out_speed)])

                else:
                    first = False

                if i+1 < len(iftraffic): i += 1
                else: break # end of data!

                in_old = in_new
                out_old = out_new
                timer_old = timer_new
                nodata = False

            else:
                # insert nodata gap in flot (this is for flot only, None is needed to display nodata gap in flot)
                out_table.append([js_timestamp_from_datetime(timezone.localtime(polls[p].dt)), None, None])
                # if no need to convert to localtime and it will be converted on the client side:
                # out_table.append([js_timestamp_from_datetime(polls[p].dt), None, None])
                nodata = False
                first = True

        return out_table

    # сначала находим интерфейс, всегда нужно для breadcrumbs
    interface = None
    try:
        if_id = int(interface_str)
        interface = Interface.objects.get(id=if_id)
    except ValueError:  # if interface_str not int!
        pass
    except Interface.DoesNotExist:
        pass
        #errors.append(u'Не могу найти указанный интерфейс: id = {0}.<p>{1}</p>'.format(if_id, e))

    if interface is None:
        try:
            interface = Interface.objects.get(if_description=interface_str)
        except Interface.DoesNotExist:
            raise Http404
            #errors.append(u'Не могу найти указанный интерфейс: id={}'.format(interface_str))
            #return render_to_response('interface.html', locals(), context_instance=RequestContext(request))

    if_id = interface.id
    dev_id = interface.dev_id_id

    # check our time_begin time_end form:
    if 'time_begin' in request.GET or 'time_end' in request.GET:
        # задан временной интервал
        form_dt = InterfaceTimeForm(request.GET)    # to prevent erasing of form's fields after request
        if form_dt.is_valid():
            time_begin = form_dt.cleaned_data['time_begin']
            time_end = form_dt.cleaned_data['time_end']
        else:
            error = u'Неверно задан временной интервал'
            return render_to_response('interface.html', locals(), context_instance=RequestContext(request))
            #return HttpResponseNotFound(error)
            #raise Http404
            #return render_to_response('interface.html', locals(), context_instance=RequestContext(request))

    else:
        # после того, как выбран интерфейс, но интервал еще не задан:
        time_begin = timezone.now() - datetime.timedelta(days=1)
        time_end = timezone.now()

        try:
            last_uptime = Sysuptime.objects.filter(dev_id=dev_id).order_by('-poll_id')[0]
            last_poll_dt = timezone.localtime(Poll.objects.get(id=last_uptime.poll_id).dt)
            time_begin = last_poll_dt - datetime.timedelta(days=1)
            time_end = last_poll_dt
        except:
            form_dt = None
            error = u'Недостаточно данных для {}. Подождите сбора статистики.'.format(interface.dev_id)
            return render_to_response('interface.html', locals(), context_instance=RequestContext(request))


    form_dt = InterfaceTimeForm(initial={'time_begin': time_begin, 'time_end': time_end})

    # find Poll:
    try:
        #Poll = Poll.objects.filter(dt__gt=time_begin)
        # it is very important to sort it!!! (sorting from model by default)
        # no QuerySet using list
        if_polls = Poll.objects.filter(dt__range=(time_begin, time_end))
    except Poll.DoesNotExist, e:
        errors.append(u'Не могу найти данные для интерфейса {0} в SQL базе.<p>{1}</p>'.format(interface, e))
        return render_to_response('interface.html', locals(), context_instance=RequestContext(request))
    #print if_polls
    #print 'total polls:', if_polls.count()

    # get interface data
    try:
        #correct way is to check all poll items:
        # it is very important to sort it!!! (sorting from model defaults)
        if_traffic = Iftraffic.objects.filter(if_id=if_id, poll_id__in=if_polls)
        #optimisation: assumpting poll.id goes one by one (need to measure!)
        #if_traffic = Iftraffic.objects.filter(if_id=if_id, poll_id__gte=if_polls[0].id, poll_id__lte=if_polls[if_polls.count()-1].id)
    except Iftraffic.DoesNotExist, e:
        if_traffic = None
        errors.append(u'Не могу найти данные для интерфейса {0} в SQL базе.<p>{1}</p>'.format(interface, e))
        return render_to_response('interface.html', locals(), context_instance=RequestContext(request))
    # sort and make lists (sorting is very important, no QuerySets - strict to lists)!
    if_polls = list(if_polls.order_by('id'))
    if_traffic = list(if_traffic.order_by('poll_id'))
    try:
        if_speed_max = max([i.if_speed for i in if_traffic])
    except:
        if_speed_max = None

    try:
        if_sysuptime = Sysuptime.objects.filter(dev_id=interface.dev_id_id,
                                            poll_id__in=[i.poll_id for i in if_traffic])
    except Sysuptime.DoesNotExist, e:
        if_sysuptime = None
        warnings.append(u'Не могу найти данные для интерфейса {0} в SQL базе:<p>{1}</p>'.format(interface, e))
    if_sysuptime = list(if_sysuptime.order_by('poll_id'))

    # save/load querry:
    ############################################################################
    #from django.core import serializers
    #serializer=serializers.get_serializer("json")()
    #out = open("sqldata.json", "w")

    ##serializer.serialize((if_polls,if_traffic,if_sysuptime), stream=out)
    #serializer.serialize(if_polls, ensure_ascii=False, stream=out)
    #out.write('\n')
    #serializer.serialize(if_traffic, ensure_ascii=False, stream=out)
    #out.write('\n')
    #serializer.serialize(if_sysuptime, ensure_ascii=False, stream=out)
    #out.close()
        #print serializer.getvalue() # for printing the result of serialization
    #from django.core import serializers
    #serializer = serializers.get_serializer("json")()
    #fh = open("sqldata.json", "r")
    #if_polls = [obj.object for obj in serializers.deserialize("json", fh.readline())]
    #if_traffic = [obj.object for obj in serializers.deserialize("json", fh.readline())]
    #if_sysuptime = [obj.object for obj in serializers.deserialize("json", fh.readline())]
    #fh.close()
    ############################################################################

    if if_sysuptime != None:
        if len(if_traffic) != len(if_sysuptime):
            warnings.append(u'Не могу использовать данные sysUpTime для интерфейса {0}: (пропущено элементов sysUpTime: {1})'
                                                        .format(interface, len(if_traffic) - len(if_sysuptime)))
            if_sysuptime = None

    if if_traffic is None or len(if_traffic) < 2:
        error = u'Нет данных для {0} в указанном временном интервале. Задайте другой временной интервал.'.format(interface)
        return render_to_response('interface.html', locals(), context_instance=RequestContext(request))

    #if_table = iftraffic_calc(if_traffic, if_polls, None, interface)
    #if_table_html_head = ['#', u'Время', u'Входящая скорость', u'Исходящая скорость']
    #if_table_html = '''<tr><th colspan="{0}" class="topheader"><b>{1}: {2}</b></th></tr>
                    #'''.format(len(if_table_html_head), interface.dev_id, interface.if_description)
    #if_table_html += html_table(if_table, if_table_html_head)

    if_table = iftraffic_jscalc(if_traffic, if_polls, if_sysuptime, interface)
    # FIXME!
    #for row in if_table:
        #if row[1] is not None:
            #js_data_in.append([js_timestamp_from_datetime(row[0]), row[1]])
        #else:
            #js_data_in.append(None)
        #if row[2] is not None:
            #js_data_out.append([js_timestamp_from_datetime(row[0]), row[2]])
        #else:
            #js_data_out.append(None)
        #jscript_data.append([js_timestamp_from_datetime(row[0]), row[1], row[2]])

    # data for javascript flot graphics
    jscript_data = json.dumps({'data': if_table,
                               'interface': {'name': interface.if_description,
                                            'device': str(interface.dev_id),
                                            'if_speed_max': if_speed_max,
                                            'description': interface.if_alias,
                                            'notes': interface.if_notes,
                                            'speed_avail': interface.if_avail_speed
                                            }
                              })

    URL_CLEAN = reverse('interface') + unicode(interface_str)
    return render_to_response('interface.html', locals(), context_instance=RequestContext(request))


def search_page(request, search_str, search_str2=None):
    ''' Database search engine
        search_str2 used only for adressbar shortcut (see urls.py)
    '''
    DEVICE_URL_PREFIX = reverse('device')
    INTERFACE_URL_PREFIX = reverse('interface')
    warnings = []
    errors = []

    def html_render(minstance, relevance):
        #full_head = [i.name for i in minstance._meta.fields]

        if minstance.__class__ is Device:
            out = '<h4><a href="{0}">{1}</a></h4>'.format(DEVICE_URL_PREFIX+str(minstance.id), minstance)
        elif minstance.__class__ is Interface:
            out = '<h4><a href="{0}">{1}</a></h4>'.format(INTERFACE_URL_PREFIX+str(minstance.id), minstance)

        out += '<p class="summary">'
        minstance_names = [i.name for i in minstance._meta.fields]  # get list of minstance fields names
        for i in minstance_names:
            item = getattr(minstance, i)  # django style getting minstance item
            out += u'{0}:{1}, '.format(i, item)
        out = out[:-2] + '</p>'
        return [out, relevance, minstance]

    def unique_items(L):
        'find unique items and return iterator'
        found = set()
        for item in L:
            if item[2] not in found: # we search for unique model instance! #return [out, relevance, minstance]
                yield item
                found.add(item[2])

    def find_devices(search_str):
        '''search for devices in database and append it to search_results
        '''
        # using relevance as weight - more is less
        try:
            dev_id = int(search_str)
            device = Device.objects.get(id=dev_id)
            relevance = 1
            search_results.append(html_render(device, relevance))
        except ValueError:
            pass
        except Device.DoesNotExist:
            pass

        try:
            device = Device.objects.get(name__iexact=search_str, eol=None)
            relevance = 2
            search_results.append(html_render(device, relevance))
        except Device.DoesNotExist:
            pass
        except Device.MultipleObjectsReturned:
            pass

        try:
            devices = Device.objects.filter(name__icontains=search_str, eol=None)
            relevance = 9
            for device in devices:
                search_results.append(html_render(device, relevance))
        except Device.DoesNotExist:
            pass

        try:
            devices = Device.objects.filter(name__icontains=search_str)
            relevance = 10
            for device in devices:
                search_results.append(html_render(device, relevance))
        except Device.DoesNotExist:
            pass
        #print search_results

    def find_interfaces(search_str, device=None):
        '''search for interfaces in database and append it to search_results
        '''
        # using relevance as weight - more is less
        try:
            if_id = int(search_str)
            if device is None:
                interface = Interface.objects.get(id=if_id)
            else:
                interface = Interface.objects.get(id=if_id, dev_id=device.id)
            relevance = 1
            search_results.append(html_render(interface, relevance))
        except ValueError:  # int(search_str)
            pass
        except Interface.DoesNotExist:
            pass

        try:
            if device is None:
                interface = Interface.objects.get(if_description__iexact=search_str)
            else:
                interface = Interface.objects.get(if_description__iexact=search_str, dev_id=device.id)
            relevance = 2
            search_results.append(html_render(interface, relevance))
        except Interface.DoesNotExist:
            pass
        except Interface.MultipleObjectsReturned:
            pass

        try:
            if device is None:
                interfaces = Interface.objects.filter(if_description__icontains=search_str)
            else:
                interfaces = Interface.objects.filter(if_description__icontains=search_str, dev_id=device.id)
            relevance = 10
            for interface in interfaces:
                search_results.append(html_render(interface, relevance))
        except Interface.DoesNotExist:
            pass
        #print search_results

    if 'search' in request.GET:
        search_str = request.GET['search']

    if search_str2 == None:
        search_words = search_str.strip().split(' ')
        if len(search_words) > 2:
            search_words = [search_str.strip(),]
    else:
        search_words = [search_str.strip(), search_str2.strip()]

    device = None
    interface = None
    search_results = []     # [['url', relevance, model_instance], ...]
    if len(search_words) == 2:
        # first word - find device(s)
        # second word - find interfaces
        find_devices(search_words[0])
        if search_results:
            # if only first device is shown:
            #device = search_results[0][2]
            #search_results = []
            #find_interfaces(search_words[1], device=device)

            # but if all devices wanted to be shown:
            # sort and remove duplicates (rewrite to one cycle)
            # remove duplicates:
            search_results = list(unique_items(search_results))
            # sorting by relevance
            search_results = sorted(search_results, key=operator.itemgetter(1))
            devices = [i[2] for i in search_results]
            search_results = []
            for device in devices:
                find_interfaces(search_words[1], device=device)

    else:
        # try to find devices:
        find_devices(search_words[0])

        # try to find interfaces:
        find_interfaces(search_words[0])

    # sort and remove duplicates (rewrite to one cycle)
    # remove duplicates:
    search_results = list(unique_items(search_results))
    # sorting by relevance
    search_results = sorted(search_results, key=operator.itemgetter(1))

    search_results_html = [i[0] for i in search_results]
    if not search_results_html:
        if search_str2 is None:
            warnings.append(u'Ничего не найдено для "{0}" :('.format(search_str))
        else:
            warnings.append(u'Ничего не найдено для "{0}:{1}" :('.format(search_str, search_str2))


    if search_str2 and search_results:
        #print INTERFACE_URL_PREFIX + str(search_results[0][2].id)
        return interface_page(request, search_results[0][2].id)
        #return redirect(INTERFACE_URL_PREFIX + str(search_results[0][2].id))

    return render_to_response('search.html', locals(), context_instance=RequestContext(request))

def tools_page(request):
    '''default page renderer
    '''
    return render_to_response('tools_main.html', locals(), context_instance=RequestContext(request))
