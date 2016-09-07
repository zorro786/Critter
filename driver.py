#
# Copyright (C) 2016 University of Southern California.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
import os
import socket
import sys
import threading
import time
import dpkt
import pymysql
import critter_settings
from stream_req_res import tcp_stream
from collections import namedtuple
from subprocess import Popen, PIPE


def tcp_flags(flag):
    res = ''
    if (flag & dpkt.tcp.TH_FIN):
        res += 'F'
    if (flag & dpkt.tcp.TH_SYN):
        res += 'S'
    if (flag & dpkt.tcp.TH_ACK):
        res += 'A'
    if (flag & dpkt.tcp.TH_PUSH):
        res += 'P'
    if (flag & dpkt.tcp.TH_RST):
        res += 'R'
    if (flag & dpkt.tcp.TH_URG):
        res += 'U'
    return res


def cnx_type(flag):
    res = ''
    if (flag & dpkt.tcp.TH_SYN):
        res = 'New'
    elif (flag & dpkt.tcp.TH_FIN):
        res = 'Close'
    elif (flag & dpkt.tcp.TH_RST):
        res = 'Abort'
    else:
        res = 'Old'
    return res


def dump_packet(pcap, sql):
    tcptuple = namedtuple('tcptuple',
                          ['source_ip', 'dest_ip', 'source_port', 'dest_port', 'conn_type', 'seq_no', 'data'])
    dump_list = []
    for hdr, payload in pcap:
        eth = dpkt.ethernet.Ethernet(payload)

        if eth.type != dpkt.ethernet.ETH_TYPE_IP:
            print "Not a valid Ethernet header"
            continue

        ip = eth.data
        if not isinstance(ip.data, dpkt.tcp.TCP):
            print "Not a TCP packet"
            continue
        tcp = ip.data
        if (tcp.sport != 80 and tcp.dport != 80):
            continue
        timestamp = hdr
        conn_type = cnx_type(tcp.flags)
        flags = tcp_flags(tcp.flags)
        payload_len = len(tcp.data)
        s_ip = str(socket.inet_ntoa(ip.src))
        d_ip = str(socket.inet_ntoa(ip.dst))
        dump_list.append((timestamp, s_ip, d_ip, str(tcp.sport), str(tcp.dport), conn_type, flags, str(tcp.seq),
                          payload_len, tcp.data))
    try:
        sql.cursor.executemany("""
                INSERT INTO Captures3(timestmp, source_ip, dest_ip, source_port, dest_port, conn_type, tcp_flags,  seq_no, plen, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                               dump_list)
        sql.conn.commit()
    except pymysql.Error as e:
        print e

def run_crawler():
    crawler = Popen('python crawler.py', stdout=PIPE, stderr=PIPE, shell=True)
    while True:
        line = crawler.stderr.readline()
        sys.stderr.write(line)


class Driver(threading.Thread):
    def __init__(self):
        super(Driver, self).__init__()
        self._stop = threading.Event()

    def run(self):

        sql = critter_settings.init()
        connections = {}  # TCP Connections Buffer
        http_states = {}  # Buffer to make HTTP stateful
        fnames = []
        for n in range(critter_settings.NO_FILES):
            fnames.append("cap.pcap" + str(n))
        fnames.sort()

        # Run crawler
        # cc = threading.Thread(target=run_crawler)
        # cc.setDaemon(True)
        # cc.start()

        while True:
            for f in fnames:
                while not self._stop.isSet():
                    while (not os.path.isfile(critter_settings.USER_DIR + "/"+f)):
                        self._stop.wait(critter_settings.SLEEP_INTERVAL)
                        if self._stop.isSet():
                            break;
                    while os.stat(critter_settings.USER_DIR + "/"+f).st_size < critter_settings.FILE_SIZE * 1000000:
                        self._stop.wait(critter_settings.SLEEP_INTERVAL)
                        if self._stop.isSet():
                            break;
                    if self._stop.isSet():
                        continue;
                    file = open(critter_settings.USER_DIR + "/"+f, 'rb')
                    pcap = dpkt.pcapng.Reader(file)
                    tcp_stream(connections, pcap, sql)
                    os.remove(critter_settings.USER_DIR + "/"+f)
                if self._stop.isSet():
                    break;
            if self._stop.isSet():
                break;

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


def test():
    sql = critter_settings.init()
    connections = {}  # TCP Connections Buffer
    fnames = []
    for n in range(critter_settings.NO_FILES):
        fnames.append("cap.pcap" + str(n))
    fnames.sort()

    # Run crawler
    # cc = threading.Thread(target=run_crawler)
    # cc.setDaemon(True)
    # cc.start()

    while True:
        for f in fnames:
            #while (not os.path.isfile(f)):
            #    time.sleep(critter_settings.SLEEP_INTERVAL)
            #while os.stat(f).st_size < critter_settings.FILE_SIZE * 1000000:
            #    time.sleep(critter_settings.SLEEP_INTERVAL)

            file = open(critter_settings.USER_DIR + "/" + "cap.pcap2", 'rb')
            pcap = dpkt.pcapng.Reader(file)
            tcp_stream(connections, pcap, sql)
            os.remove(f)

