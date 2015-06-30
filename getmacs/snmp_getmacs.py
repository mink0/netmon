#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
# Version 3 /11.2011 by Mikhail Mekhanov
# Changelog:
# v3:   interface rewritten using classes
#       using pysnmp instead of netsnmp

'''Usage: %prog [options] ADDRESS [GW_ADDRESS]
Show MAC address tables using Net-SNMP engine to collect data from SNMP devices.
Visit http://www.net-snmp.org/ to get Net-SNMP binaries. 
Note: GW_ADDRESS is gateway address and used for binding MAC addresses with IP.
Request order (for Cisco):
1) vtpVlanState (.1.3.6.1.4.1.9.9.46.1.3.1.1.2) - VLAN table
2) dot1dTpFdbAddress (.1.3.6.1.2.1.17.4.3.1.1) - MAC adress table for each VLAN
3) dot1dTpFdbPort (.1.3.6.1.2.1.17.4.3.1.2) - the bridge port number for each VLAN
4) dot1dBasePortIfIndex (.1.3.6.1.2.1.17.1.4.1.2) - convert bridge port to ifindex
5) ifName (.1.3.6.1.2.1.31.1.1.1.1) - get the name of interface by ifindex
KNOWN ISSUES: Cisco - no macs for "no switchport" interfaces :(
'''

import sys
import optparse
import operator     # for smart sorting
from datetime import datetime

from mypysnmp import snmpwalk, snmpget, SnmpError

# Module defaults
SNMPVER = 1             # deafult snmp version for vendor request
COMMUNITY = 'public'   #'public'    # default snmp ro community string
DOMAIN = None           # deafult domain name
MAC_DELIMITER = ':'     # ':' # Char to fill beetween the bytes of mac-address

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
    'vtpVlanState': '.1.3.6.1.4.1.9.9.46.1.3.1.1.2',        # id.vlan = status
    # ciscoCdpMIB
    'cdpCacheDeviceId': '1.3.6.1.4.1.9.9.23.1.2.1.1.6',     # id.port =  cdp device name
    'cdpCacheDevicePort': '1.3.6.1.4.1.9.9.23.1.2.1.1.7',
    'cdpCachePlatform': '1.3.6.1.4.1.9.9.23.1.2.1.1.8'
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

    def get_cdp_nbs(self, address=None, community=None, snmpver=None):
        '''getting interface table with full interface names and descriptions
        '''
        if address is None:
            address = self.address
        if community is None:
            community = self.community
        if snmpver is None:
            snmpver = self.snmpver

        rs_ifnames = snmpwalk(address, OIDS['ifName'], community, snmpver, exception=False)
        rs_devs = snmpwalk(address, OIDS['cdpCacheDeviceId'], community, snmpver, exception=False)
        rs_dtypes = snmpwalk(address, OIDS['cdpCachePlatform'], community, snmpver, exception=False)
        rs_rports = snmpwalk(address, OIDS['cdpCacheDevicePort'], community, snmpver, exception=False)

        max_items = max(rs_devs['oid'], rs_dtypes['oid'], rs_rports['oid'])
        cdp_table = []

        def get_id(oid):
            return oid.split('.')[-2] + '.' + oid.split('.')[-1]

        for item in max_items:
            row = {
                'ifname': None,
                'dev': None,
                'type': None,
                'rport': None
            }

            row['ifid'] = get_id(item)  # id is unique

            for i in xrange(len(rs_ifnames['oid'])):
                if item.split('.')[-2] == rs_ifnames['oid'][i].split('.')[-1]:
                    row['ifname'] = rs_ifnames['value'][i]
                    break
            for i in xrange(len(rs_devs['oid'])):
                if row['ifid'] == get_id(rs_devs['oid'][i]):
                    row['dev'] = rs_devs['value'][i]
                    break
            for i in xrange(len(rs_dtypes['oid'])):
                if row['ifid'] == get_id(rs_dtypes['oid'][i]):
                    row['type'] = rs_dtypes['value'][i]
                    break
            for i in xrange(len(rs_rports['oid'])):
                if row['ifid'] == get_id(rs_rports['oid'][i]):
                    row['rport'] = rs_rports['value'][i]
                    break

            cdp_table.append(row)

        #print cdp_table
        return cdp_table


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
        rsAdmin = snmpwalk(address, OIDS['ifAdminStatus'], community, snmpver, exception=False)
        rsOper = snmpwalk(address, OIDS['ifOperStatus'], community, snmpver, exception=False)

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
            for ii in xrange(len(rsAdmin['oid'])):
                if iface['ifid'] == rsAdmin['oid'][ii].split('.')[-1]:
                    iface['ifadm'] = rsAdmin['value'][ii]
                    break
            for ii in xrange(len(rsOper['oid'])):
                if iface['ifid'] == rsOper['oid'][ii].split('.')[-1]:
                    iface['ifoper'] = rsOper['value'][ii]
                    break
            iftable.append(iface)

        #print iftable
        return iftable
    
    def _convert_mac(self, ordval):
        '''simple converter from binary data to a HexString represenation
        '''
        return MAC_DELIMITER.join(['{0:02x}'.format(ord(x)) for x in ordval])

    def get_vlans_cisco(self, address=None, community=None, snmpver=None):
        '''VLAN table data collection
        returns list of vlans
        '''
        if address is None:
            address = self.address
        if community is None:
            community = self.community
        if snmpver is None:
            snmpver = self.snmpver
        
        # works for Cisco devices:
        rs = snmpwalk(address, OIDS['vtpVlanState'], community, snmpver, exception=True)    # id.vlan = status
        self.collect_vlans = True
        vlans = []
        # for i in rs['oid']:
        #     vlans.append(i.split('.')[-1])
        # print vlans
        return [i.split('.')[-1] for i in rs['oid']]

    def get_mactable(self, address=None, community=None, snmpver=None, vlans=[None, ]):
        '''MAC address table data collection
        returns list of instances of empty class with attributes:
        .ifid .ifmac .vlan'''

        if address is None:
            address = self.address
        if community is None:
            community = self.community
        if snmpver is None:
            snmpver = self.snmpver
        
        #!FIXME testing - first iteration without vlans
        #if vlans != [None, ]:
        #   vlans.insert(0, None)
        
        mactable = []
        mac_changed = False     # True if MAC Address table is changed during collecting
        for vlan in vlans:
            if vlan:
                rsA = snmpwalk(address, OIDS['dot1dTpFdbAddress'], community + '@' + str(vlan), snmpver, exception=True)    # id.mac = mac
                rsP = snmpwalk(address, OIDS['dot1dTpFdbPort'], community + '@' + str(vlan), snmpver, exception=False)      # id.mac = port (ifid)
                rsPI = snmpwalk(address, OIDS['dot1dBasePortIfIndex'], community + '@' + str(vlan), snmpver, exception=False)   # bport = ifindex
            else:
                rsA = snmpwalk(address, OIDS['dot1dTpFdbAddress'], community, snmpver, exception=True)        # id.mac = mac
                rsP = snmpwalk(address, OIDS['dot1dTpFdbPort'], community, snmpver, exception=False)          # id.mac = bport
                rsPI = snmpwalk(address, OIDS['dot1dBasePortIfIndex'], community, snmpver, exception=False)   # bport = ifindex

            max_items = max(rsA['oid'], rsP['oid'])  #, rsS.iid)
            #print max_items
            for i in max_items:
                mac_obj = {
                    'ifid': None,
                    'mac': None,
                    'vlan': vlan
                    #'status': None,
                }

                id = i[len(OIDS['dot1dTpFdbAddress']):]   # get id. id is the same for rsA and rsP

                # find MAC:
                for ii in xrange(len(rsA['oid'])):
                    if id in rsA['oid'][ii]:
                        try:
                            mac_obj['mac'] = self._convert_mac(rsA['varBinds'][ii][0][1])
                        except TypeError:
                            self.log_write('* WARNING! Unknown value in MAC address table: ' + rsA['value'][ii])
                            continue
                        break
                # find bport:
                for ii in xrange(len(rsP['oid'])):
                    if id in rsP['oid'][ii]:
                        bport = rsP['value'][ii].strip() # bridge port is usually equal to ifindex, but ->
                        #print 'bport: ', bport 
                        for pi in xrange(len(rsPI['oid'])): # -> we need translate bport to ifindex 
                            #print rsPI['oid'][pi].split('.')[-1].strip()
                            #print rsPI['oid'][pi][len(OIDS['dot1dBasePortIfIndex']):]
                            if bport == rsPI['oid'][pi].split('.')[-1].strip():
                               mac_obj['ifid'] = rsPI['value'][pi]
                               #print 'mac_obj.ifid', mac_obj.ifid
                        break
                
                if mac_obj['ifid'] is None or mac_obj['mac'] is None: # or mac_obj.status is None
                    mac_changed = True
                
                mactable.append(mac_obj)
        
        #print('found:', len(mactable))
        if mac_changed:
            self.log_write('* ВНИАНИЕ! Таблица MAC адресов устройства изменилась во время сбора статистики. Чтобы получить последние данные можете обновить страницу.')
        
        return mactable

    def get_arptable(self, address=None, community=None, snmpver=None):
        '''ARP address table data collection
        returns list of empty class instances with such attributes:
        .mac .ipaddr'''

        if address is None:
            address = self.address
        if community is None:
            community = self.community
        if snmpver is None:
            snmpver = self.snmpver
        
        rsM = snmpwalk(address, OIDS['ipNetToMediaPhysAddress'], community, snmpver, exception=True)  # id.mac = mac
        rsI = snmpwalk(address, OIDS['ipNetToMediaNetAddress'], community, snmpver, exception=False)  # id.mac = port (ifid)
        max_items = max(rsM['oid'], rsI['oid'])

        arptable = []
        mac_changed = False     # True if MAC Address table is changed
        for i in max_items:
            arp_obj = {
                'ipaddr': None,
                'mac': None
            }

            id = i[len(OIDS['ipNetToMediaPhysAddress']):]   # id is unique; function of ip address 
            
            for ii in xrange(len(rsM['oid'])):
                if id in rsM['oid'][ii]:   # find mac
                    # print(rsM['varBinds'][ii][1])
                    try:
                        arp_obj['mac'] = self._convert_mac(rsM['varBinds'][ii][0][1])
                    except TypeError:
                        self.log_write('* WARNING! Unknown value in MAC address table: ' + rsA['value'][ii])
                    break
            for ii in xrange(len(rsI['oid'])):
                if id in rsI['oid'][ii]:
                    arp_obj['ipaddr'] = rsI['value'][ii]
                    break

            if arp_obj['mac'] is None or arp_obj['ipaddr'] is None:
                mac_changed = True

            arptable.append(arp_obj)

        if mac_changed:
            self.log_write('* Warning! ARP address table has changed during data collection. Try again to get the actual one.')
        return arptable


def ioctl_GWINSZ(fd): #### TABULATION FUNCTIONS
    '''another way to determine terminal size'''
    try: ### Discover terminal width
        import fcntl, termios, struct, os
        cr = struct.unpack('hh',
        fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        return None
    return cr
def terminal_size2():
    '''another way to determine terminal size'''
    # try open fds
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
    # ...then ctty
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
    if not cr:
    # env vars or finally defaults
        try:
            cr = (env['LINES'], env['COLUMNS'])
        except:
            cr = (25, 80)
    return int(cr[0]), int(cr[1])


def terminal_size():
    '''dumb method to determine actual terminal window size'''
    import subprocess
    try:
        rows, columns = subprocess.Popen('stty size', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().split()
        rows, columns = int(rows), int(columns)
    except:     # windows and other compatibility
        rows, columns = 25, 80
    return rows, columns


def main():
    class Struct:pass
    parser = optparse.OptionParser(usage=__doc__)
    parser.add_option("-c",
                      help="snmp agent's community", default=COMMUNITY, dest="community", metavar="COMMUNITY")
    parser.add_option("-v",
                      help="snmp version: default is %default", default=SNMPVER, dest="snmpver", metavar="VERSION")
    parser.add_option("-f",
                      action="store_true", dest="file", default=False,
                      help="store output in file")
    parser.add_option("-q",
                      action="store_true", dest="verbose", default=False,
                      help="verbose output")
    (opts, args) = parser.parse_args()
    opts.address = None
    opts.gwaddress = None
    collect_vlans = False

    if len(args) < 1:
        parser.error('no address specified')
    elif len(args) > 1:
        opts.gwaddress = args[1]
    if opts.community is None:
        parser.error('no community specified')
    opts.address = args[0]
    if not '.' in opts.address and DOMAIN:    # sometimes very useful :)
        opts.address += DOMAIN

    if opts.verbose: print('* Trying the host {0}...'.format(opts.address))
    device = SnmpDevInfo(opts.address, opts.community, opts.snmpver)
    device.get_sysdescr()
    if 'Cisco' in device.sysdescr:
        collect_vlans = True
    if opts.verbose: print(device.sysdescr)
    rows, columns = terminal_size()
    device.get_sysname()
    print(device.sysname.center(columns))
    print(device.sysdescr.splitlines()[0][:columns].center(columns))

    if opts.verbose: print('* Getting interface table...')
    iftable = device.get_iftable()
    if opts.verbose:
        print('-' * columns)
        for i in iftable: print(i)
        print('-' * columns)

    if opts.verbose: print('* Getting MAC address table...')
    if collect_vlans:
        mactable = device.get_mactable(vlans=device.get_vlans_cisco())
    else:
        mactable = device.get_mactable()
    for i in device.log_pop():  # print errors and warnings
        print i
    if opts.verbose:
        print('-' * columns)
        for i in mactable: print(i)
        print('-' * columns)

    if opts.verbose: print('* Getting ARP address table from {0}...'\
                        .format(opts.gwaddress if opts.gwaddress else opts.address))
    if opts.gwaddress:
        arptable = device.get_arptable(address=opts.gwaddress)
    else:
        arptable = device.get_arptable()
    for i in device.log_pop():  # print errors and warnings
        print i
    if opts.verbose:
        print('-' * columns)
        for i in arptable: print(i)
        print('-' * columns)

    if opts.verbose: print("* It's done! Forming output table...")
    # forming output table:
    if collect_vlans:
        table_header = ['#', 'ID', 'IfName', 'Vlan', 'MAC', 'IP', 'Description']
    else:
        table_header = ['#', 'ID', 'IfName', 'MAC', 'IP', 'Description']
        
    table = []
    for macitem in mactable:
        id = ''
        if macitem['ifid']:    # Port SNMP ID != None
            try:
                id = int(macitem['ifid'])   # for accurate sorting
            except: pass
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
            table.append([id, ifname, macitem['vlan'], macitem['mac'], ip, alias])
        else:
            table.append([id, ifname, macitem['mac'], ip, alias])

    # sorting by ID
    table = sorted(table, key=operator.itemgetter(0))
    if not table:
        raise MyError('No data! SNMP-mib not supported for this device')
    for i in xrange(len(table)):
        if table[i][0] != '':
            table[i][0] = '.' + str(table[i][0])
        table[i].insert(0, i + 1) # insert index
    table.insert(0, table_header) # add header

    rows, columns = terminal_size()
    # manual width counting:
    #width = (columns-(3+4+18+16))//2
    #if width < 1: width = 1

    # auto adjust width for table to fit in terminal window:
    try:
        for i in [0] + range(30, 1, -1):
            if i != 0 and i < 10:
                lB = '|'; rB = '|'; b = '|'     # shorter table
            else:
                lB = '| '; rB = ' |'; b = ' | ' # pretty table but longer...
            out_table = formatTable(table, topHeader=True, separateRows=2, 
                            leftBorder=lB, rightBorder=rB, border=b, width=i)
            tablelen = out_table.find('\n')
            if columns - tablelen > 1:
                break
    except:
        print 'Error in formating output table:'
        print '-' * columns
        print `table`
        print '-' * columns
        raise
    
    if columns-tablelen > 1:
        padder = ' ' * ((columns -tablelen) // 2)
        for i in out_table.splitlines():
            print(padder + i)
    else: 
        print(out_table)
        
    if opts.file:
        fname = '{0}_{1}.txt'.format(device.sysname, datetime.now().strftime('%d-%m-%y.%H-%M'))

        ftable = []     # skip first row - id not needed for files and hard to compare
        for row in table:
            nrow = []
            for i in xrange(1, len(row)):
                nrow.append(row[i])
            ftable.append(nrow)
        lB = '| '; rB = ' |'; b = ' | ';
        out_table = formatTable(ftable, topHeader=True, separateRows=2, 
                        leftBorder=lB, rightBorder=rB, border=b)
        fh = open(fname, 'w')
        fh.write(out_table)
        fh.close()
        print '{0} was created: {1}'.format(fname, fh)


if __name__ == '__main__':
    try:
        main()
    except MyError as exception:
        print(exception)
        sys.exit(2)
        #exception.printerror()
        #print type(exception)     # the exception instance
        #print exception.args      # arguments stored in .args
        #print sys.exc_info()[0]
    except SnmpError as exception:
        print(exception)
        sys.exit(2)

