#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
# Version v2 05.2011 by Mikhail Mekhanov
'''Usage: %prog [options] ADDRESS IFACENAME
Print interface's current transfer rate using Net-SNMP engine to collect data 
from SNMP device. Visit http://www.net-snmp.org/ to get Net-SNMP binaries.
'''
import sys
import optparse
import time
import subprocess
from time import sleep

## This one is simple Net-SNMP wrapper provided by Net-SNMP since 5.4 version
## <libsnmp-python> packet in debian
## import netsnmp 
# using my analog instead, 'cos netsnmp python wrapper is still not finsished:
from mypysnmp import snmpwalk, snmpget, SnmpError
#from mytable import formatTable

# Module defaults
SNMPVER = '1'           # deafult snmp version for vendor request
COMMUNITY = 'public'   #'public'    # default snmp ro community string
UPDTIME = 5             # default update time
DOMAIN = None           # deafult domain name

OIDS = {
    'sysName': '.1.3.6.1.2.1.1.5.0',
    'sysDescr': '.1.3.6.1.2.1.1.1.0',
    'sysUpTime': '.1.3.6.1.2.1.1.3.0',
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
    # MAC Address Table:
    'dot1dTpFdbAddress': '.1.3.6.1.2.1.17.4.3.1.1',     # id.mac = mac
    'dot1dTpFdbPort': '.1.3.6.1.2.1.17.4.3.1.2',        # id.mac = bport (bport - bridge port. bport = 0 if destination unknown or self; bport number not equal ifindex)
    'dot1dBasePortIfIndex': '.1.3.6.1.2.1.17.1.4.1.2',  # bport = ifindex (for every vlan!)
    'dot1dTpFdbStatus': '.1.3.6.1.2.1.17.4.3.1.3',      # id.mac = status (1 - other, 2 - invalid, 3 - learned, 4 - self, 5 - mgmt)
    # ARP Table (ipNetToMediaTable) deprecated. Soon will be replaced by ipNetToPhysicalTable, ipv4InterfaceTable, ipv6InterfaceTable 
    'ipNetToMediaIfIndex': '.1.3.6.1.2.1.4.22.1.1',     # id.ip = port
    'ipNetToMediaPhysAddress': '.1.3.6.1.2.1.4.22.1.2', # id.ip = mac
    'ipNetToMediaNetAddress': '.1.3.6.1.2.1.4.22.1.3',  # id.ip = ip
    'ipNetToMediaType': '.1.3.6.1.2.1.4.22.1.4',        # id.ip = type (3 - dynamic, 4 - static)
    # Deprecated ARP Table: 
    'atPhysAddress': '.1.3.6.1.2.1.3.1.1.2',    # ARP Table: id.ip = mac (deprecated)
    'atIfIndex': '.1.3.6.1.2.1.3.1.1.1',        # ARP Table: id.ip = ifindex (deprecated)
    # VLAN list (enterprise Cisco-mib):
    'vtpVlanState': '.1.3.6.1.4.1.9.9.46.1.3.1.1.2',    # id.vlan = status
    }

class MyError(Exception):
    '''base class for all exceptions raised by this module
    '''
    def __str__(self):
        return '{0}.{1}: {2}'.format(__name__, self.__class__.__name__, self.args[0])

# заготовка для будущей библиотеки
class SnmpDevInfoError(Exception):
    '''base class for all exceptions raised by this module
    '''
    def __str__(self):
        return '{0}.{1}: {2}'.format(__name__, self.__class__.__name__, self.args[0])

# заготовка для будущей библиотеки
class SnmpDevInfo():
    '''all general methods is here. may be used as a stand-alone module
    '''
    def __init__(self, address, community=COMMUNITY, snmpver=SNMPVER):
        self.address = address
        self.community = community
        self.snmpver = snmpver
        self.log = []   # simple log
        
        # initial check
        if not self.address:
            raise SnmpDevInfoError('no address specified')
        elif not self.community:
            raise SnmpDevInfoError('no community specified')
        if DOMAIN and '.' not in self.address:      # sometimes very useful :)
            self.address += DOMAIN

    def log_write(self, record):
        '''write to log
        '''
        self.log.append(record)

    def log_pop(self):
        '''iterator to read and remove record from log. usage: for i in log_pop(): print i
        '''
        while len(self.log) > 0:
            yield self.log.pop(0)

    def log_read(self):
        '''read entire log and reset it
        '''
        log = self.log
        self.log = []
        return log

    def get_sysname(self):
        '''get agent sysname
        '''
        rs = snmpget(self.address, OIDS['sysName'], self.community, self.snmpver, exception=True)
        self.sysname = rs['value']
        return self.sysname

    def get_sysdescr(self):
        '''get agent sysdescr and trivial detect of Cisco device
        '''
        rs = snmpget(self.address, OIDS['sysDescr'], self.community, self.snmpver, exception=True)
        self.sysdescr = rs['value']
        return self.sysdescr
    
    def get_iftable(self, address=None, community=None, snmpver=None):
        '''getting interface table with full interface names and descriptions
        '''
        if address is None:
            address = self.address
        if community is None:
            community = self.community
        if snmpver is None:
            snmpver = self.snmpver
        
        rsN = snmpwalk(address, OIDS['ifName'], community, snmpver, exception=False)
        rsA = snmpwalk(address, OIDS['ifAlias'], community, snmpver, exception=False)
        rsD = snmpwalk(address, OIDS['ifDescr'], community, snmpver, exception=False)
        
        max_items = max(rsN['oid'], rsA['oid'], rsD['oid'])
        
        iftable = []
        for i in max_items:
            iface = {
                'ifid': None,
                'ifname': None,
                'ifalias': None,
                'ifdescr': None
            }
            
            iface['ifid'] = i.split('.')[-1]  # id is unique port number

            for ii in xrange(len(rsN['oid'])):
                if iface['ifid'] == rsN['oid'][ii].split('.')[-1]:
                    iface['ifname'] = rsN['value'][ii]
                    break
            for ii in xrange(len(rsA['oid'])):
                if iface['ifid'] == rsA['oid'][ii].split('.')[-1]:
                    iface['ifalias'] = rsA['value'][ii]
                    break
            for ii in xrange(len(rsD['oid'])):
                if iface['ifid'] == rsD['oid'][ii].split('.')[-1]:
                    iface['ifdescr'] = rsD['value'][ii]
                    break
            iftable.append(iface)

        #print iftable
        return iftable

def terminal_size():
    '''dumb method to determine actual terminal window size'''
    import subprocess
    try:
        rows, columns = subprocess.Popen('stty size', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().split()
        rows, columns = int(rows), int(columns)
    except:
        rows, columns = 25, 79
    return rows, columns

class SnmpIfInfo(SnmpDevInfo):
    '''all specific methods is here
    '''
    def _convert_speed(self, inspeed):
        '''simplest network rate unit converter
        '''
        units = ''
        if inspeed >= 1e15:
           inspeed = inspeed / 1e15
           units = 'P'
        elif inspeed >= 1e12:
           inspeed = inspeed / 1e12
           units = 'T'
        elif inspeed >= 1e9:
           inspeed = inspeed / 1e9
           units = 'G'
        elif inspeed >= 1e6:
           inspeed = inspeed / 1e6
           units = 'M'
        else:
           inspeed = inspeed / 1e3
           units = 'k'
        # pretty output: kickoff .0 endings
        if str(inspeed).endswith('.0'):
           inspeed = int(inspeed)
        return inspeed, units

    def _sort_natural(self, string):
        '''A natural sort helper function for sort() and sorted()
        without using regular expression.

        >>> items = ('Z', 'a', '10', '1', '9')
        >>> sorted(items)
        ['1', '10', '9', 'Z', 'a']
        >>> sorted(items, key=_sort_natural)
        ['1', '9', '10', 'Z', 'a']
        '''
        r = []
        for c in string:
            try:
                c = int(c)
                try: r[-1] = r[-1] * 10 + c
                except: r.append(c)
            except:
                r.append(c)
        return r

    def get_ifnametable(self):
        '''get interface table dict: [ifindex] <-> [ifname]
           version 2 (slower, need to fetch two tables)
        '''
        self.ifnametable = {}
        rs = snmpwalk(self.address, OIDS['ifName'], self.community, self.snmpver)
        #if len(rs['value']) == 0 or len([i for i in rs['value'] if rs['value'].count(i) > 1]) > 0:
        rs1 = snmpwalk(self.address, OIDS['ifInOctets'], self.community, self.snmpver, exception=True) # этот массив будет меньше или равен предыдущему и будет содержать только те интерфейсы, с которых может собираться статистика
        oid_table = {}
        for i in xrange(len(rs1['value'])):
            oid_table[rs1['oid'][i].split('.')[-1]] = rs1['oid'][i].split('.')[-1]
        if len(rs['value']) != 0:
            # добавляем дескрипшены к oid_table там, где это возможно
            descr_table = {}
            for i in xrange(len(rs['value'])):
                descr_table[rs['value'][i]] = rs['oid'][i].split('.')[-1]
            self.ifnametable = {}
            for k, v in oid_table.iteritems():
                #keyname = [key for key, val in descr_table.iteritems() if val == v]
                keyname = next((key for key, val in descr_table.iteritems() if val == v), None)
                if keyname:
                    self.ifnametable[keyname] = v
                else:
                    self.ifnametable[k] = v

        else:
            self.ifnametable = oid_table

        # else:
        #     for i in xrange(len(rs['value'])):
        #         self.ifnametable[rs['value'][i]] = rs['oid'][i].split('.')[-1]
        return self.ifnametable

    def get_ifmaxspeed(self, if_name=None, if_id=None):
        if if_id:
            self.if_id = str(if_id)
        else:
            if hasattr(self, 'if_id'):
                if_id = self.if_id
            else:
                if if_name is None:
                    if hasattr(self, 'if_name'):
                        if_name = self.if_name
                    else:
                        raise MyError('no interface specified!')
                if_id = self.find_interface_id(if_name)
                
        rs = snmpget(self.address, '{0}.{1}'.format(OIDS['ifSpeed'], if_id), self.community, 
                                                                        self.snmpver, exception=True)
        try:
            self.ifspeed_max = int(rs['value'])
        except:
            self.ifspeed_max = None
            raise MyError("can't get maxspeed with interface id = {0}, oid = {1}".
                        format(if_id, '{0}.{1}'.format(OIDS['ifSpeed'], if_id)))
        if self.ifspeed_max >= 4 * 1e9: 
            # experimental and dirty, need to improve
            rs = snmpget(self.address, '{0}.{1}'.format(OIDS['ifHighSpeed'], if_id), self.community, 
                                                                        self.snmpver, exception=True)
            self.ifspeed_max = int(rs['value']) * 1e6
        return self.ifspeed_max

    def find_interface_id(self, if_name):
        'find if_id for specific interface'
        if_name = str(if_name)
        if not hasattr(self, 'iftable'):
            self.get_ifnametable()
        # exact if_name search (case sensitive):
        for i in self.ifnametable:
            if i == if_name:
                self.if_id = self.ifnametable[i]
        if not hasattr(self, 'if_id'):
            # rough if_name search (case insensitive):
            for i in self.ifnametable:
                if  if_name.lower() in i.lower():
                    self.if_id = self.ifnametable[i]
        if not hasattr(self, 'if_id'):
            raise MyError("can't find specified interface {0} at {1}".format(repr(if_name), repr(self.address)))
        # save for further use (for speed)
        self.if_name = if_name
        return self.if_id
    
    def if_check64(self, if_name=None):
        '''returns true if 64 bit counters can be used (useful for high speed interfaces)
        '''
        if if_name is None:     # use already saved data
            if hasattr(self, 'if_name'):
                if_name = self.if_name
            else:
                raise MyError('no interface specified to poll')
            if not hasattr(self, 'if_id'):
                self.find_interface_id(if_name)     # find if_id
        else:
            self.find_interface_id(if_name)     # find if_id
            
        try:
            rs = snmpget(self.address, '{0}.{1}'.format(OIDS['ifHCInOctets'], self.if_id),
                                                    self.community, self.snmpver, exception=True)
        except SnmpError:    # no data recieved
            self.use64bit = False

        if not rs['value']:
            self.use64bit = False
        else:
            self.use64bit = True
        return self.use64bit


    def get_ifbytes(self, if_name=None, if_id=None, force64bit=False,):
        '''get interface octets: .ifInOctets, .ifOutOctets, sysUptime,ifInErrors, ifOutErrors
           if_name = None to skip id searching (no additional requests for looped polls)
        '''
        if if_id:
            self.if_id = str(if_id)
        else:
            if if_name is None:     # use already saved data, used for looped polls
                if hasattr(self, 'if_name'):
                    if_name = self.if_name
                else:
                    raise MyError('no interface specified to poll')
                if not hasattr(self, 'if_id'):
                    self.find_interface_id(if_name)     # find if_id
                    force64bit = self.if_check64()  # ne pomeshaet :)
            else:
                self.find_interface_id(if_name)     # find if_id
                force64bit = self.if_check64()  # ne pomeshaet :)
        
        sysUpTime = OIDS['sysUpTime']
        if force64bit:
            ifinoctets = OIDS['ifHCInOctets']
            ifoutoctets = OIDS['ifHCOutOctets']
        else:
            ifinoctets = OIDS['ifInOctets']
            ifoutoctets = OIDS['ifOutOctets']
            
        rs = snmpget(self.address, (
                ifinoctets + '.' + self.if_id,
                ifoutoctets + '.' + self.if_id,
                sysUpTime,
                OIDS['ifInErrors'] + '.' + self.if_id,
                OIDS['ifOutErrors'] + '.' + self.if_id,
        ), self.community, self.snmpver, exception=True)
        
        # save for further use (for looped polls)
        self.if_name = if_name
        return rs

    def get_ifrate(self, if_name=None, if_id=None, req_delay=5, force64bit=False):
        '''get interface rate: InSpeed, OutSpeed, .sysUptime
           Делаем два запроса, по ним считаем скорость. Без повторов, без проверки на ошибки.
           Остальное делаем вне, что дает нам возможность обрабатывать все ошибки.
           При ошибках вылетают exception.
           if_name = None to skip id searching (no additional requests for looped polls)
           req_delay - delay between two queries in sec
           timeout - maximum delay
        '''
        req_delay = int(req_delay)
        
        #if if_id:
            #self.if_id = if_id

        # counter zeroing:
        if force64bit:
            maxcount = 2**64 - 1     
        else:
            if hasattr(self, 'use64bit') and self.use64bit:
                maxcount = 2**64 - 1
            else:
                maxcount = 2**32 - 1

        # we need two successfull queries to calculate interface tx/rx rate
        rs1 = self.get_ifbytes(if_name=if_name, if_id=if_id)
        sleep(req_delay)
        rs2 = self.get_ifbytes(if_name=if_name, if_id=if_id)
        
        in_old = int(rs1['value'][0])
        out_old = int(rs1['value'][1])
        timer_old = int(rs1['value'][2])
        in_new = int(rs2['value'][0])
        out_new = int(rs2['value'][1])
        timer_new = int(rs2['value'][2])
        
        upd_interval = (timer_new - timer_old) / 100.
        if upd_interval > 0:
            in_speed = 8. * (in_new - in_old) / upd_interval    # from octets to bits per second
            out_speed = 8. * (out_new - out_old) / upd_interval
            # counter zeroing
            if in_speed < 0:
                in_speed = 8. * (in_new + maxcount - in_old) / upd_interval
            if out_speed < 0:
                out_speed = 8. * (out_new + maxcount - out_old) / upd_interval
        else:
            # no data will be calculated. 
            #FIXME!
            # we can use local time instead of sysuptime...
            in_speed = None
            out_speed = None
            sysuptime = None
        
        outdata = {'in_speed':in_speed, 'out_speed':out_speed, 'sysuptime':timer_new}
        return outdata

    def get_ifrate_forced(self, if_name=None, if_id=None, req_delay=5, timeout=30, force64bit=False):
        '''get interface rate: inSpeed, outSpeed, sysUptime, inErrors, outErrors
           # повторяем запросы до тех пор, пока не получим два успешных ответа. по ним считаем скорость.
           if_name = None to skip id searching (no additional requests for looped polls)
           req_delay - delay between two queries in sec
           timeout - maximum delay
        '''
        req_delay = int(req_delay)
        timeout = int(timeout)
        # use already saved data. used for looped polls
        if not if_name and hasattr(self, 'if_name'):
            if_name = self.if_name
        if not if_id and hasattr(self, 'if_id'):
            if_id = self.if_id

        if not if_id:
            if not if_name:
                raise MyError('no interface specified to poll')
            else:
                self.find_interface_id(if_name)     # find if_id
                force64bit = self.if_check64()      # ne pomeshaet :)
        # save for further use in looped polls
        self.if_name = if_name
        self.if_id = if_id

        # we need two successfull queries to calculate interface tx/rx rate
        in_old = 0
        out_old = 0
        timer_old = 0
        noprint = True
        stab_time = 1                           # stabilization time, if device become too busy
        if force64bit: maxcount = 2**64 - 1     # for counter zeroing
        else: maxcount = 2**32 - 1
        while 1:
            try:
                rs = self.get_ifbytes(if_name=if_name)
            except SnmpError, exception:     # no data recieved
                # stop watching:
                #if stab_time > 10:
                #    print '\n',exception
                #    raise MyError('device is too busy or inaccessible')
                noprint = True  # wait for device to become stable
                sleep(stab_time * req_delay)
                if stab_time * req_delay <= timeout:
                    stab_time *= 2
                    continue
                else:
                    raise MyError('timeout!')
            stab_time = 1
            in_new = int(rs['value'][0])
            out_new = int(rs['value'][1])
            timer_new = int(rs['value'][2])
            in_err = int(rs['value'][3])
            out_err = int(rs['value'][4])
            upd_interval = (timer_new - timer_old) / 100.
            if upd_interval <= 0:
                noprint = True
            in_speed = 8. * (in_new - in_old) / upd_interval    # from octets to bits per second
            out_speed = 8. * (out_new - out_old) / upd_interval
            # counter zeroing
            if in_speed < 0:
                in_speed = 8. * (in_new + maxcount - in_old) / upd_interval
            if out_speed < 0:
                out_speed = 8. * (out_new + maxcount - out_old) / upd_interval

            in_old = in_new
            out_old = out_new
            timer_old = timer_new

            if not noprint:
                break   # end of the loop and data is ready
            else:
                sleep(req_delay)
            noprint = False

        outdata = {'in_speed':in_speed, 'out_speed':out_speed, 'sysuptime':timer_new, 'in_errors': in_err, 'out_errors': out_err}
        return outdata


def progressbar(cur_val, min_val=0, max_val=100, width=80, blchar='#', spchar='.', mode=2):
   'simple progress bar generator'
   out= ''
   # simple error checking, skip it if necessary
   if min_val == max_val:
       return out
   if cur_val < min_val:
       cur_val = min_val
   if cur_val > max_val:
       cur_val = max_val

   if mode == 1:   # simple progress bar
       width -= 2
       out = (int(round((1.0 * width * (cur_val - min_val) / max_val))) * blchar).ljust(width, spchar)
       out = '[' + out + ']'
   if mode == 2:   # progress bar + percent counter
       width -= 6
       out = (int(round((1.0 * width * (cur_val - min_val) / max_val))) * blchar).ljust(width, spchar)
       out = '[' + out + ']'
       out += (str(int(round(100. * (cur_val - min_val) / max_val))) + '%').ljust(4)
   return out


def main():
    parser = optparse.OptionParser(usage=__doc__)
    parser.add_option("-c",
                      help="snmp agent's community", default=COMMUNITY, dest="community", metavar="COMMUNITY")
    parser.add_option("-v",
                      help="snmp version: default is %default", default=SNMPVER, dest="snmpver", metavar="VERSION")
    parser.add_option("-u",
                      help="update interval: default is %default", dest="updtime", default=UPDTIME, metavar="SECONDS")
    parser.add_option("-m",
                      help="set maximum bandwidth manually", dest="maxspeed", default=None, metavar="BITS/S")
    parser.add_option("--64",
                      help="force to use 64 bit counters", action="store_true", dest="use64bit", default=False)
    parser.add_option("-g", "--hist",
                      action="store_false", dest="hist", default=True,
                      help="histogram mode")
    parser.add_option("-t",
                      action="store_true", dest="histT", default=False,
                      help="histogram mode with timestamps")
    parser.add_option("-l",
                      action="store_true", dest="list", default=False,
                      help="list index of available interfaces")
    parser.add_option("-q",
                      action="store_true", dest="verbose", default=False,
                      help="verbose output")
    (opts, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("no address specified")

    opts.address = args[0]
    opts.updtime = int(opts.updtime)
    if len(args) > 1:
        opts.if_name = args[1]
    else:
        opts.if_name = None
    if opts.address is None:
        parser.error("no address specified")
    elif opts.community is None:
        parser.error("no community specified")
#######################################################################################################################

    if opts.verbose: print('* Trying the host {0}...'.format(opts.address))
    poller = SnmpIfInfo(opts.address, opts.community, opts.snmpver)
    poller.get_sysdescr()
    if opts.verbose: print poller.sysdescr
    
    rows, columns = terminal_size()
    if opts.verbose: print '* Getting interface table...'
    poller.get_ifnametable()
    
    if opts.if_name:
        try:
            poller.find_interface_id(opts.if_name)
        except MyError: pass
    if not hasattr(poller, 'if_id') or opts.verbose or opts.list:
        print 'Available interface list:'
        print '-' * columns
        print sorted(poller.ifnametable, key=poller._sort_natural)
        print '-' * columns
    if opts.list:
        from modules.mytable import formatTable
        print 'Detailed interface list:'
        iftable = poller.get_iftable()
        labels = ('ifIndex', 'ifName', 'ifAlias', 'ifDescr')
        table = []
        for i in iftable:
            table.append([i['ifid'], i['ifname'], i['ifalias'], i['ifdescr']])
        # autofit table width:
        for i in [0] + range(30, 1, -1):
            outTable = formatTable([labels] + table, separateRows=2, border='|',
                                            leftBorder='|', rightBorder='|', width=i)
            tablelen = outTable.find('\n')
            if columns-tablelen > 1:
                break
        print outTable
        sys.exit()
    if not hasattr(poller, 'if_id'):
        if opts.if_name: raise
        else: raise MyError('no interface specified')

    poller.get_sysname()
    print poller.sysname.center(columns)
    print poller.sysdescr.splitlines()[0][:columns].center(columns)
    print '-' * columns
    rs = snmpget(poller.address, OIDS['ifDescr'] + '.' + poller.if_id, poller.community, poller.snmpver)
    poller.ifdescr = rs['value']
    s = rs['value']
    rs = snmpget(poller.address, OIDS['ifAlias'] + '.' + poller.if_id, poller.community, poller.snmpver)
    poller.ifalias = rs['value']
    s += ': "' + rs['value'] + '"'
    print(s)
    try:
        rs = snmpget(poller.address, ('{0}.{1}'.format(OIDS['ifAdminStatus'], poller.if_id),
            '{0}.{1}'.format(OIDS['ifOperStatus'], poller.if_id)), poller.snmpver, exception=True)
    except SnmpError:
        poller.if_admin_status = None
        poller.if_op_status = None
    else:
        print rs
        poller.if_admin_status = rs['value'][0]
        poller.if_op_status = rs['value'][1]
        if not '1' in poller.if_admin_status or not '1' in poller.if_op_status:
            print 'Warning: ifAdminStatus:', poller.if_admin_status
            print 'Warning: ifOperStatus:', poller.if_op_status
    print('-' * columns)

    if not opts.maxspeed:
        poller.get_ifmaxspeed()
    else:
        poller.ifspeed_max = int(opts.maxspeed)

    speed, units = poller._convert_speed(poller.ifspeed_max)
    try:
        rs = snmpget(poller.address, OIDS['ifInErrors'] + '.' + poller.if_id,
                                            poller.community, poller.snmpver, exception=True)
    except SnmpError:
        poller.ifinerrors = '?'
    else:
        poller.ifinerrors = int(rs['value'])

    try:
        rs = snmpget(poller.address, OIDS['ifOutErrors'] + '.' + poller.if_id,
                                            poller.community, poller.snmpver, exception=True)
    except SnmpError:
        poller.ifouterrors = '?'
    else:
        poller.ifouterrors = int(rs['value'])
    
    if opts.use64bit:
        use64bit = True
    elif getattr(poller, 'ifspeed_max', 0) >= 1e9:  # try to use 64bit counters on gigabit interfaces
        use64bit = poller.if_check64()
    else:
        use64bit = False

    if use64bit:
        s = '64 |'
    else: s = ''
    print '| Spd:', speed, units + 'bit/s', '| iErr:', str(poller.ifinerrors), '| oErr:',\
                                str(poller.ifouterrors), '| Upd:', str(opts.updtime)+'s', '|', s
    
###############################################################################################################    
    #rs = poller.get_ifrate(req_delay=1, if_id = 1)
    #print rs
    #sys.exit()
###############################################################################################################    
    
    noprint = False
    stab_time = 1
    while 1:
        rows, columns = terminal_size()
        try:
            data = poller.get_ifrate(req_delay=opts.updtime, force64bit=use64bit)
        except SnmpError as ei:    # no data recieved
            # stop watching:
            #if stab_time > 600:
            #    print '\n', ei
            #    raise MyError('device is too busy or inaccessible')
            noprint = True  # wait for device to become stable
            sleep(stab_time * opts.updtime)
            if stab_time * opts.updtime < 600:
                stab_time *= 2
            #continue
        stab_time = 1
        
        in_speed = data['in_speed']
        out_speed = data['out_speed']

        if None in data:
            noprint = True
        
        if noprint is False:
            in_speed_str, in_units = poller._convert_speed(in_speed)
            out_speed_str, out_units = poller._convert_speed(out_speed)
            if round(in_speed_str, 1) < 10:
                in_speed_str = 'In:  ' + str(round(in_speed_str,1)).rjust(3) + ' ' + in_units + 'bit/s'
            else: # kick off unnecessary decimals
                in_speed_str = 'In:  ' + str(int(round(in_speed_str))).rjust(3) + ' ' + in_units + 'bit/s'
            if round(out_speed_str, 1) < 10:        
                out_speed_str = 'Out: ' + str(round(out_speed_str,1)).rjust(3) + ' ' + out_units + 'bit/s'
            else:
                out_speed_str = 'Out: ' + str(int(round(out_speed_str))).rjust(3) + ' ' + out_units + 'bit/s'
            # prepare timestamps
            if opts.histT:
                out = '|' + time.strftime('%H:%M:%S') + '|'
                i = (columns - len(in_speed_str + out_speed_str) - 4 - len(out)) // 2
            else:
                out = ''
                i = (columns - len(in_speed_str + out_speed_str) - 4) // 2

            out += in_speed_str + ' ' + progressbar(in_speed, max_val=poller.ifspeed_max, width=i)
            out += '  '
            out += out_speed_str + ' ' + progressbar(out_speed, max_val=poller.ifspeed_max, width=i)
        else:
            out = 'Collecting data...'

        # add endings for non-scrolling output
        if not (opts.hist or opts.histT):
            out += ' ' * (columns - len(out) - 1) + '\r'
        else: 
            out += ' ' * (columns - len(out) - 1) + '\n'
        sys.stdout.write(out)
        sys.stdout.flush()
        noprint = False

if __name__ == '__main__':
    try:
        main()
    except MyError as exception:
        print exception
        sys.exit(2)
        #exception.printerror()
        #print type(exception)     # the exception instance
        #print exception.args      # arguments stored in .args
        #print sys.exc_info()[0]
    except (SnmpError, SnmpDevInfoError) as ei:
        print ei
        sys.exit(2)
