#!/usr/bin/python2.7
'''
Simple pysnmp interface. Supports snmpv1 snmpv2c get, getbulk & getnext queries
API: http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-v2c.html
Version 04.2014
CHANGELOG:
  04.2014:
  [+] support for pysnmp 4.2.4
        changed error handling algorytm
        new way of cmdGen call
        lookupNames=False
TODO:
  [-] str2tuple need to be removed, native strings support is implemented
'''
      

from __future__ import print_function

# Module defaults
SNMPVER = '2'           # deafult snmp version for request
COMMUNITY = 'public'   #None    # default snmp ro community string

import sys
from pysnmp.entity.rfc3413.oneliner import cmdgen

class SnmpError(Exception):
    """Base class for all exceptions raised by this module.
    """
    def __str__(self):
        return '{0}.{1}: {2}'.format(__name__, self.__class__.__name__, self.args[0])


def snmpwalk(address, oids, community=COMMUNITY, version=SNMPVER, exception=False):
    'simple wrapper. may be changed in future'
    return snmpget(address, oids, community, version, exception, __cmd='snmpwalk')


def snmpget(address, oids, community=COMMUNITY, version=SNMPVER, exception=False, __cmd='snmpget'):
    '''Run Net-SNMP:snmpget and return formated data'''
    outdata = {
        'errorIndication': None,
        'errorStatus': None,
        'errorIndex': None,
        'varBinds': None,
        'oid': [],
        'value': []
        }
    
    def str2tuple(oid):
        'translate string-oids to tuple-oids'
        oid_obj = []
        for i in oid.split('.'):
            if i != '': # skips leading/trailing dots
                oid_obj.append(int(i))
        return tuple(oid_obj)
    
    version = str(version)      # v3 support not yet implemented
    if version == '1':
        mpModel = 0
    else:
        mpModel = 1

    #print oids
    
    single_oid = False
    if isinstance(oids, (str, unicode)):    # single string
        single_oid = True
        oids = (str2tuple(oids),)
    else:
        # list of strings, list of oid-list, oid-list
        new_oids = []
        for oid in oids:
            if isinstance(oid, (str, unicode)): # tuple of strings
                new_oids.append(str2tuple(oid))
            else:
                new_oids.append(oid)
        oids = tuple(new_oids)
        try:
            if not oids[0][0]: pass
        except TypeError:   # single oid-list
            single_oid = True
            oids = (oids, )

    #print oids
    cmdGen = cmdgen.CommandGenerator()
    
    if __cmd == 'snmpget':
        pysnmp_cmd = cmdGen.getCmd
    else:
        pysnmp_cmd = cmdGen.nextCmd
        
    try:
        errorIndication, errorStatus, errorIndex, varBinds = pysnmp_cmd(
            cmdgen.CommunityData('mypysnmp', community, mpModel),   # for snmp version support
            #cmdgen.CommunityData(community),
            cmdgen.UdpTransportTarget((address, 161)),
            *oids,
            #cmdgen.MibVariable('SNMPv2-MIB', 'sysDescr', 0),
            lookupNames=False, # oids as numbers,
            lookupValues=True # translate PyASN1 objects to strings
        )
    except:
        # unfortunately there are some exceptions happen
        errorIndication = '{0}: {1}'.format(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        errorStatus = ''
        errorIndex = ''
        varBinds = []
        
    outdata['errorIndication'] = errorIndication
    outdata['errorStatus'] = errorStatus
    outdata['errorIndex'] = errorIndex
    outdata['varBinds'] = varBinds
        
    if errorIndication:
        # single oid request
        if exception:
            raise SnmpError(errorIndication)
        else:
            print(errorIndication, file=sys.stderr)
    else:
        if errorStatus:
            # bulk request: error in one oid from group of oids
            if exception:
                raise SnmpError('{0} at {1}'.format(errorStatus, errorIndex and varBinds[int(errorIndex)-1] or '?'))
            else:
                #print('%s at %s' % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1] or '?'))
                print('{0} at {1}'.format(errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1] or '?'), file=sys.stderr)
        else:
            if __cmd == 'snmpget':
                for name, val in varBinds:
                    outdata['oid'].append(name.prettyPrint())
                    outdata['value'].append(val.prettyPrint())
            else:
                for varBindTableRow in varBinds:
                    for name, val in varBindTableRow:
                        #print(name._MibVariable__oid)
                        outdata['oid'].append(name.prettyPrint())
                        outdata['value'].append(val.prettyPrint())
    
    # we don't need a tuple when only one element is asked
    if single_oid and __cmd == 'snmpget' and not errorIndication and not errorStatus:
        outdata['oid'] = outdata['oid'][0]
        outdata['value'] = outdata['value'][0]
    return outdata


if __name__ == '__main__':
    # tests
    rs = snmpget('demo.snmplabs.com', (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 18, 1), 'public', exception=False)
    print('> OK! RESULT:\n', rs['value'], rs['oid'])

    # rs = snmpget('ikk-net56-sw2', (1,3,6,1,2,1,1,1,0), 'public', 1, exception=False)
    # print('> OK! RESULT:\n', rs['value'])
    #
    # try:
    #     rs = snmpget('cc-net1-sw1', ((1,3,6,1,2,1,1,1,0), (1,3,6,1,2,1,1,1,0)), 'public', exception=True)
    #     print('> OK! RESULT:\n', rs['value'])
    #
    #     rs = snmpget('cc-net1-sw1', '1.3.6.1.2.1.1.1.0', exception=True)
    #     print('> OK! RESULT:\n', rs['value'])
    #
    #     rs = snmpget('core22-adm', ('.1.3.6.1.2.1.1.1.0', '.1.3.6.1.2.1.1.4.0'), 'public', 2, exception=True)
    #     print('> OK! RESULT:\n', rs['value'])
    #
    #     rs = snmpwalk('core22-adm', '.1.3.6.1.2.1.4.22.1.2', 'public', exception=True)
    #     print('> OK! RESULT:\n', rs['value'])
    # except SnmpError as e:
    #     print(e)
