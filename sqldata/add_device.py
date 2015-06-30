#!/usr/bin/python
# Version 05.2010
# FIXME: when you add 64 bit counter you should test if this available


'''Usage: %prog [options] IPADDRESS
Add node to PostgeSQL for snmp poller (yuray database)'''

import sys
import optparse
from time import sleep
import datetime
import re
import psycopg2
import psycopg2.extras
import multiprocessing
import random
# netsnmp python wrapper is still not finsished, using my analog instead:
sys.path.append('/usr/local/bin')  # path to mynetsnmp parser
from modules.mypysnmp import snmpwalk, snmpget, SnmpError
from modules.mytable import formatTable

# Module defaults
SNMPVER = '2c'  # deafult snmp version for vendor request
COMMUNITY = 'public'  #'public'    # default snmp ro community string
DOMAIN = None  # deafult domain name

#IF_FILTER = '^[^nu][^lo][^vl][^stack]'    # default interface filter
IF_FILTER = r'^nu|^nv|^vl|^lo|^stack|^fa[0-9]$'

# database access
SQL_SERVER = 'istat-db'
SQL_PORT = '5433'
SQL_DATABASE = 'core_collect_m'
SQL_USER = 'minko'
SQL_PASS = '567890'
# database table names
SQL_DEVTABLE = 'devices'
SQL_INTERFACES = 'interfaces'
SQL_DATA = 'snmpdata'
COUNTER_BITS = '64'

OID = {
    "sysName": '.1.3.6.1.2.1.1.5.0',
    "sysUpTime": '.1.3.6.1.2.1.1.3.0',
    "sysDescr": '.1.3.6.1.2.1.1.1.0',
    "ifDescr": '.1.3.6.1.2.1.2.2.1.2',  # full interface name
    "ifName": '.1.3.6.1.2.1.31.1.1.1.1',  # interface name
    "ifSpeed": '.1.3.6.1.2.1.2.2.1.5',  # maximum speed of interface
    "ifHighSpeed": '.1.3.6.1.2.1.31.1.1.1.15',  # maximum speed of interface in mbits
    "ifAlias": '.1.3.6.1.2.1.31.1.1.1.18',  # interface description
    "ifInOctets": '.1.3.6.1.2.1.2.2.1.10',
    "ifHCInOctets": '.1.3.6.1.2.1.31.1.1.1.6',  # 64 bit counter
    "ifOutOctets": '.1.3.6.1.2.1.2.2.1.16',
    "ifHCOutOctets": '.1.3.6.1.2.1.31.1.1.1.10',  # 64 bit counter
    "ifInErrors": '.1.3.6.1.2.1.2.2.1.14',
    "ifOutErrors": '.1.3.6.1.2.1.2.2.1.20',
    "ifAdminStatus": '.1.3.6.1.2.1.2.2.1.7',
    "ifOperStatus": '.1.3.6.1.2.1.2.2.1.8',
    "sysObjectID": '1.3.6.1.2.1.1.2.0'
}


class MyError(Exception):
    """Base class for all exceptions raised by this module.
    """

    def __init__(self, value):
        self.error = value

    def __str__(self):
        return str(self.error)

    def printerror(self):
        print '\n' + __name__ + ': error:', self.error


def speedconvert(inspeed):
    'simple units converter'
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


def getifdtable(address, community, snmpver, filter=IF_FILTER):
    '''getting interface table with full interface names and descriptins
    returns list of empty class instances with such attributes:
    .ifindex .ifname .ifalias .ifdescr'''

    class Struct:
        pass

    iftable = []

    rs_name = snmpwalk(address, OID["ifName"], community, snmpver, exception=False)
    rs_alias = snmpwalk(address, OID["ifAlias"], community, snmpver, exception=False)
    rs_descr = snmpwalk(address, OID["ifDescr"], community, snmpver, exception=False)
    rs_speed = snmpwalk(address,OID["ifSpeed"], community, snmpver, exception=False)
    rs_hspeed = snmpwalk(address,OID["ifHighSpeed"], community, snmpver, exception=False)
    rs_bit64 = snmpwalk(address,OID["ifHCInOctets"], community, snmpver, exception=False)
    #rs_adm = snmpwalk(address,OID["ifAdminStatus"], community, snmpver, exception=False)
    #rs_op = snmpwalk(address,OID["ifOperStatus"], community, snmpver, exception=False)

    max_iid = max(rs_name['oid'], rs_alias['oid'], rs_descr['oid'])

    for i in max_iid:
        ifitem = Struct()  # create array of struct type C analog
        ifitem.ifoid = None
        ifitem.ifindex = None
        ifitem.ifname = None
        ifitem.ifalias = None
        ifitem.ifdescr = None
        ifitem.iffiltered = False

        ifitem.ifoid = i
        ifitem.ifindex = i.split('.')[-1]  # id is unique port number
        for ii in xrange(len(rs_name['oid'])):
            if ifitem.ifindex == rs_name['oid'][ii].split('.')[-1]:
                ifitem.ifname = rs_name['value'][ii]
                break
        for ii in xrange(len(rs_alias['oid'])):
            if ifitem.ifindex == rs_alias['oid'][ii].split('.')[-1]:
                ifitem.ifalias = rs_alias['value'][ii]
                break
        for ii in xrange(len(rs_descr['oid'])):
            if ifitem.ifindex == rs_descr['oid'][ii].split('.')[-1]:
                ifitem.ifdescr = rs_descr['value'][ii]
                break

        for ii in xrange(len(rs_descr['oid'])):
            if ifitem.ifindex == rs_speed['oid'][ii].split('.')[-1]:
                if int(rs_speed['value'][ii]) < 4294967295:
                    ifitem.ifspeed = int(rs_speed['value'][ii])
                    break
            if ifitem.ifindex == rs_hspeed['oid'][ii].split('.')[-1]:
                ifitem.ifspeed = int(rs_hspeed['value'][ii]) * 10**6
                break

        speed, units = speedconvert(ifitem.ifspeed)
        ifitem.ifspeed = str(speed) + ' ' + units + 'bit/s'


        if ifitem.ifindex in [i.split('.')[-1] for i in rs_bit64['oid']]:
            ifitem.bit64 = True
        else:
            ifitem.bit64 = False

        if re.search(filter, ifitem.ifname, re.IGNORECASE):
            ifitem.iffiltered = True
        iftable.append(ifitem)

        #for i in iftable:
        #print i.__dict__
    #sys.exit()
    return iftable


def mysortkey(string):
    r'''A natural sort helper function for sort() and sorted()
    without using regular expression.

    >>> items = ('Z', 'a', '10', '1', '9')
    >>> sorted(items)
    ['1', '10', '9', 'Z', 'a']
    >>> sorted(items, key=mysortkey)
    ['1', '9', '10', 'Z', 'a']
    '''
    r = []
    for c in string:
        try:
            c = int(c)
            try:
                r[-1] = r[-1] * 10 + c
            except:
                r.append(c)
        except:
            r.append(c)
    #print r
    return r


def terminal_size():
    '''dumb method to determine actual terminal window size'''
    import subprocess

    try:
        rows, columns = subprocess.Popen('stty size', shell=True, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).stdout.read().split()
        rows, columns = int(rows), int(columns)
    except:  # for compatibility with windows (and others)
        rows, columns = 25, 79
    return rows, columns


def SQLcollector(address, opts):
    #print(address)
    if opts.verbose: print '* Discover type of the host...'
    rs = snmpget(address, OID["sysDescr"], opts.community, opts.snmpver)
    opts.sysdescr = rs['value']
    if opts.verbose: print opts.sysdescr
    rows, columns = terminal_size()
    if opts.verbose:
        print '* Getting interface table...'
    ifdtable = []
    table = []
    ifdtable = getifdtable(address, opts.community, opts.snmpver, opts.filter)
    if opts.list or opts.verbose:
        print 'Detailed interface list:'
        labels = ('ifIndex', 'ifName', 'ifAlias', 'ifDescr', 'ifSpeed', '64bit counters')
        for i in ifdtable: table.append([i.ifindex, i.ifname, i.ifalias, i.ifdescr, i.ifspeed, i.bit64])
        # autofit table width:
        for i in [0] + range(30, 1, -1):
            outTable = formatTable([labels] + table, separateRows=2, border='|', leftBorder='|', rightBorder='|',
                                   width=i)
            tablelen = outTable.find('\n')
            if columns - tablelen > 1: break
        print outTable
    if opts.list:
        sys.exit()

    rs = snmpget(address, OID['sysName'], opts.community, opts.snmpver, exception=False)
    opts.sysname = rs['value']
    rs = snmpget(address, OID['sysObjectID'], opts.community, opts.snmpver, exception=False)
    opts.sys_object_id = rs['value']
    #print rs.__dict__

    print (opts.sysname + ':' + opts.sys_object_id).center(columns)
    print opts.sysdescr.splitlines()[0][:columns].center(columns)
    print '-' * columns

    sql_conn = psycopg2.connect("host={0} dbname={1} user={2} password={3} port={4}".format(SQL_SERVER,
                                                                                            SQL_DATABASE, SQL_USER,
                                                                                            SQL_PASS, SQL_PORT))
    sql_cur = sql_conn.cursor()

    # check if main device table exists
    sql_cur.execute("select * from information_schema.tables where table_name=%s", (SQL_DEVTABLE,))
    if sql_cur.rowcount == 0:
        raise MyError('> "{0}" table not found!'.format(SQL_DEVTABLE))

    dev_found = False
    if not opts.force_add:
        # check if device exist!
        # find device
        sql_cur.execute("SELECT * FROM devices WHERE ip_mgmt = %s", (address,))  # check value
        if sql_cur.rowcount != 0:
            devices = sql_cur.fetchall()
            for dev in devices:
                #print dev
                if dev[6] == None:
                    dev_found = True
                    device_id = dev[0]

    if not dev_found:
        print '> Creating new device in {0}...'.format(SQL_DEVTABLE)
        sql_cur.execute("""INSERT INTO devices (ip_mgmt, community, name, sys_object_id) 
                            VALUES (%s, %s, %s, %s) RETURNING id""",
                        (address, opts.community, opts.sysname, opts.sys_object_id))
        device_id = sql_cur.fetchone()[0]
        print sql_cur.statusmessage
        sql_conn.commit()
        #sql_cur.execute("SELECT * FROM devices WHERE ip_mgmt = %s", (address,))  # get id
        #device_id = sql_cur.fetchone()[0]
    else:
        print '\n> {} is found in DB with dev_id={}! No device is added...\n'.format(address, device_id)
    #sql_cur.execute("SELECT (id) FROM devices WHERE ip_mgmt = %s", (address,))  # check value


    # open SQL_INTERFACES table:
    sql_cur.execute("SELECT * FROM information_schema.tables WHERE table_name = %s", (SQL_INTERFACES,))
    if sql_cur.rowcount == 0:
        raise MeError('> "{0}" table not found!'.format(SQL_INTERFACES))


    # delete old interface list from SQL_INTERFACES table
    #sql_cur.execute('DELETE FROM {0} WHERE device_id_fk = {1};'.format(SQL_INTERFACES, device_id))

    # get inerfaces for current device:
    sql_cur.execute("SELECT (if_index) FROM interfaces WHERE dev_id = %s", (device_id,))
    sql_iftable = sql_cur.fetchall()

    # save only new interfaces in our SQL_INTERFACES table
    print '> Trying to find new interfaces for the dev_id={0}, ip={1}:'.format(device_id, address)
    ifname_lst = [i.ifname for i in ifdtable]

    for ifitem in ifdtable:  # loop through interfaces
        # skip all filtered interfaces:
        if ifitem.iffiltered:
            print '>..skipping {0}: filtered by {1}'.format(ifitem.ifname, opts.filter)
            continue

        idname = ifitem.ifname

        # find our interface in sql database and add new if needed
        #print sql_iftable
        #print [i[0] for i in sql_iftable]
        #print ifitem.ifindex
        if [str(i[0]) for i in sql_iftable].count(str(ifitem.ifindex)) == 0:
            sql = '''INSERT INTO {0} (dev_id, if_index, if_description, if_counter_capacity, enable_collect, if_alias)
                                        VALUES (%s, %s, %s, %s, %s, %s)'''.format(SQL_INTERFACES)
            timestamp = datetime.datetime.now()
            bits = '32'
            if opts.bits == '64' and ifitem.bit64:
                bits = '64'
            vars = (device_id, ifitem.ifindex, idname, bits, 'true', ifitem.ifalias)
            sql_cur.execute(sql, vars)
            print '>..adding new interface {0} ::{1}bits'.format(idname, bits)
            print sql_cur.statusmessage
        else:
            print '>..interface {0} already exist!'.format(idname)
    sql_conn.commit()

    sql_cur.close()
    sql_conn.close()


def main():
    parser = optparse.OptionParser(usage=__doc__)
    parser.add_option("-c",
                      help="snmp agent's community", default=COMMUNITY, dest="community", metavar="COMMUNITY")
    parser.add_option("-v",
                      help="snmp version: default is %default", default=SNMPVER, dest="snmpver", metavar="VERSION")
    parser.add_option("-d",
                      help="scan for new interfaces using default filter: " + IF_FILTER,
                      action="store_true", dest="ifdetect", default=False)
    parser.add_option("--filter",
                      help="using regexp to filter unwanted interfaces, default is: %default",
                      action="store", dest="filter", default=IF_FILTER)
    parser.add_option("-f", action="store", dest="hfile", default=None,
                      help="Read addresses from file. Syntax is simple: one line - one address", metavar="FILE")
    parser.add_option("--32",
                      help="force to use 32 bit counters", action="store_true", dest="bit32", default=False)
    parser.add_option("-l",
                      action="store_true", dest="list", default=False,
                      help="list index of available interfaces")
    parser.add_option("--force",
                      help="force add new device without checking in existing devices", action="store_true",
                      dest="force_add", default=False)
    parser.add_option("-q",
                      action="store_true", dest="verbose", default=False,
                      help="verbose output")
    (opts, args) = parser.parse_args()

    #args = ['172.20.1.2',] # for debug

    opts.hosts = args
    opts.bits = COUNTER_BITS

    if len(args) < 1 and opts.hfile is None:
        parser.error("no address specified")
    if opts.hfile is not None:
        fh = open(opts.hfile, 'r')
        opts.hosts = [i.strip() for i in fh.readlines()]
    if not opts.community:
        parser.error('no community name specified')
    if opts.bit32:
        opts.bits = '32'
    for host in opts.hosts:
        if host.find('.') == -1 and DOMAIN != None:  # sometimes very useful :)
            opts.hosts[index(host)] += DOMAIN
    
    rows, cols = terminal_size()            
    for host in opts.hosts:
        if len(host) > 0 and not host.startswith('#'):
            print ('.' * ((cols - len(host))/2) + host + '.' * ((cols - len(host))/2))
            SQLcollector(host, opts)


if __name__ == '__main__':
    try:
        main()
    except MyError, exception:
        exception.printerror()
        sys.exit(2)
    except SnmpError, exception:
        exception.printerror()
        sys.exit(2)
