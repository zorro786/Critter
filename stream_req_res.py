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
import logging
import socket
import sqlite3
import dpkt
from StringIO import StringIO
from critter_settings import settings
from http import *


MAX_RECORDS_RETRIEVE = 1000000
FETCH_SLEEP_TIMEOUT = 10
CXN_TIMEOUT_VALUE = 1800

stream_logger = logging.getLogger("StreamLogger")
stream_logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
stream_logger.addHandler(ch)


class ConnectionObject():
    def __init__(self, start, end, client_iseq, server_iseq, ts, cxntype):
        """
        :param start: Time stamp of the first packet
        :param end: Time stamp of the last packet after closing connection
        :param client_iseq: Initial sequence number of client
        :param server_iseq: Initial sequence number of server
        :param ts: Time stamp of last packet
        :param cxntype: New or Old or Close
        :return:
        """
        self.start = start
        self.end = end
        self.client_iseq = client_iseq
        self.server_iseq = server_iseq
        self.request_buffer = {}
        self.response_buffer = {}
        self.last_seen = ts
        self.last_cxntype = cxntype


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


def process_timeout(sql):
    while True:
        #        time.sleep(FETCH_SLEEP_TIMEOUT)
        try:
            sql.cursor.execute("""SELECT no, timestmp, last_seen, source_ip, dest_ip, source_port, dest_port, conn_type, tcp_flags, seq_no, data FROM Captures
                        WHERE processed = 'N' AND conn_type = 'New' and (UNIX_TIMESTAMP() - last_seen) > %s LIMIT %s""",
                               (CXN_TIMEOUT_VALUE, MAX_RECORDS_RETRIEVE))
        except sqlite3.Error as e:
            stream_logger.info(str(e))
        if sql.cursor.rowcount < MAX_RECORDS_RETRIEVE:
            time.sleep(FETCH_SLEEP_TIMEOUT)
            continue
        rows = sql.cursor.fetchall()
        rows = [r for r in rows]
        rownum = [row[0] for row in rows]
        pkts = []
        for row in rows:
            try:
                sql.cursor.execute("""SELECT no, timestmp, last_seen, source_ip, dest_ip, source_port, dest_port, conn_type, tcp_flags, seq_no, data from Captures
                                    WHERE processed = 'N' and conn_type = 'Old' AND (timestmp BETWEEN %s AND %s) AND source_ip = %s AND dest_ip = %s AND source_port = %s
                                    AND  dest_port = %s""", (row[1], row[2], row[3], row[4], row[5], row[6]))
            except sqlite3.Error as e:
                print e
            res = sql.cursor.fetchall()
            rownum += [r[0] for r in res]
            pkts += res
        result = rows + pkts
        sql.cursor.executemany("UPDATE Captures SET processed = 'Y' where no = %s", rownum)
        sql.conn.commit()
        yield (sorted(result, key=lambda x: x[1]))


"""
    for key in connections.keys():
        if (time.time() - connections[key].last_seen) > to_value:
            combined_data = build_stream(connections[key].request_buffer, connections[key].response_buffer)
            if(combined_data is not None):
                parse_http(combined_data, connections[key].start, connections[key].end)
                del connections[key]
"""

'''
    while True:
        try:
            sql.cursor.execute("""SELECT timestmp, source_ip, dest_ip, source_port, dest_port, conn_type, tcp_flags, seq_no, data FROM Captures3
                            limit %s, %s""", (start, MAX_RECORDS_RETRIEVE))
        except pymysql.Error as e:
                print e
        packets = sql.cursor.fetchall()
        count = sql.cursor.rowcount
        if(count == 0):
            return
            #time.sleep(FETCH_SLEEP_TIMEOUT)
            #continue
        start += count
'''


def tcp_stream(connections, pcap, sql):
    """
    This function parses TCP packets from the pcap file and creates connections in a dictionary
    :param connections: dict to hold ConnectionObject
    :param pcap: dpkt Reader instance
    :param sql: SQLite connection instance
    :return:
    """
    tcptuple = namedtuple('tcptuple',
                          ['timestmp', 'source_ip', 'dest_ip', 'source_port', 'dest_port', 'conn_type', 'tcp_flags',
                           'seq_no', 'data'])
    start = 0
    for hdr, payload in pcap:

        try:
            eth = dpkt.ethernet.Ethernet(payload)
        except dpkt.dpkt.NeedData as e:
            print e
            continue
        if eth.type != dpkt.ethernet.ETH_TYPE_IP:
            stream_logger.info("Not a valid Ethernet header.")
            continue

        try:
            ip = eth.data
            if not isinstance(ip.data, dpkt.tcp.TCP):
                stream_logger.info("Not a TCP Packet.")
                continue
            tcp = ip.data
        except:
            continue

        if (tcp.sport != 80 and tcp.dport != 80):
            continue

        packet = (hdr, str(socket.inet_ntoa(ip.src)), socket.inet_ntoa(ip.dst), str(tcp.sport), str(tcp.dport),
                  cnx_type(tcp.flags), tcp_flags(tcp.flags), tcp.seq, tcp.data)
        tt = tcptuple(*packet)
        key1 = tt.source_ip + ":" + tt.source_port
        key2 = tt.dest_ip + ":" + tt.dest_port
        if (key1 < key2):
            key = (key1, key2)
        else:
            key = (key2, key1)
        if (tt.conn_type == "New" and tt.tcp_flags == "S"):
            connections[key] = ConnectionObject(start=tt.timestmp, end=None, client_iseq=tt.seq_no, server_iseq=None,
                                                ts=tt.timestmp, cxntype="New")
        elif (connections.has_key(key) and connections[key].server_iseq is None):
            connections[key].server_iseq = tt.seq_no
            connections[key].last_seen = tt.timestmp
            connections[key].last_cxntype = "New"
        elif (tt.conn_type == "Old" or tt.conn_type == "Close") and connections.has_key(key) and len(tt.data) > 0:
            if (len(connections[
                        key].request_buffer) > 150000):  # Roughly 1500 bytes per TCP packet puts a limit of around 150 MB file transfer
                del (connections[key])
                stream_logger.info("Deleted a connection with %s packets" % len(connections[key].request_buffer))
                continue
            if (tt.source_port == '80'):
                offset = int(tt.seq_no) - int(connections[key].server_iseq)
                if (not connections[key].response_buffer.has_key(offset)):
                    connections[key].response_buffer[offset] = (tt.timestmp, tt.data)
                    connections[key].end = connections[key].last_seen = tt.timestmp
                    connections[key].last_cxntype = "Old"
                else:
                    stream_logger.debug("Duplicate Packet")
            else:
                offset = int(tt.seq_no) - int(connections[key].client_iseq)
                if (not connections[key].request_buffer.has_key(offset)):
                    connections[key].request_buffer[offset] = (tt.timestmp, tt.data)
                    connections[key].end = connections[key].last_seen = tt.timestmp
                    connections[key].last_cxntype = "Old"
                else:
                    stream_logger.debug("Duplicate Packet")
        elif (tt.conn_type == "Abort" and connections.has_key(key)):
            del (connections[key])
        elif (tt.conn_type == "Old" and connections.has_key(key) and connections[key].last_cxntype != "Close"):
            connections[key].last_cxntype = "Old"
        elif (tt.conn_type == "Close" and connections.has_key(key)):
            connections[key].last_cxntype = "Close"
    dump_list = []

    last_id = sql.get_last_session_ids()
    if (last_id is not None):
        tcp_id = last_id
    else:
        stream_logger.debug("Unable to retrieve last tcp id used, skipping the current file")
        return

    for key, value in connections.items():
        f = bool(value.last_cxntype == "Close")
        t = bool(time.time() - float(value.last_seen) > CXN_TIMEOUT_VALUE)

        if (f or t):
            if (bool(value.request_buffer) and bool(value.response_buffer)):
                combined_data = build_stream(value.request_buffer, value.response_buffer)
                if (combined_data is not None):
                    tcp_id += 1
                    dump_list = dump_list + parse_http(combined_data, key, tcp_id)
                    del (connections[key])
                else:
                    stream_logger.info("Missing Segments")
                    del (connections[key])
            else:
                del (connections[key])
    stream_logger.info("Number of HTTP packets assembled %s" % len(dump_list))
    for dump in dump_list:
        sql.insert_query(dump)
    try:
        sql.cursor.close()
        sql.connection.close()
        sql.cursor = None
        sql.connection = None
    except sqlite3.Error as e:
        stream_logger.debug(str(e))


def build_stream(request_buffer, response_buffer):
    """
    This function builds the TCP streams to create HTTP streams.
    :param request_buffer: Dictionary of requests
    :param response_buffer: Dictionary of responses
    :return: Merged requests and responses buffers sorted on timestamp
    """
    request_data = []
    response_data = []

    # request block copied from dpkt http module
    request = (
        'GET', 'PUT', 'ICY',
        'COPY', 'HEAD', 'LOCK', 'MOVE', 'POLL', 'POST',
        'BCOPY', 'BMOVE', 'MKCOL', 'TRACE', 'LABEL', 'MERGE',
        'DELETE', 'SEARCH', 'UNLOCK', 'REPORT', 'UPDATE', 'NOTIFY',
        'BDELETE', 'CONNECT', 'OPTIONS', 'CHECKIN',
        'PROPFIND', 'CHECKOUT', 'CCM_POST',
        'SUBSCRIBE', 'PROPPATCH', 'BPROPFIND',
        'BPROPPATCH', 'UNCHECKOUT', 'MKACTIVITY',
        'MKWORKSPACE', 'UNSUBSCRIBE', 'RPC_CONNECT',
        'VERSION-CONTROL',
        'BASELINE-CONTROL'
    )
    response = ("HTTP/",)

    # Sort by Sequence Number
    request_sorted_keys = sorted(request_buffer.keys())
    n1 = len(request_sorted_keys)

    response_sorted_keys = sorted(response_buffer.keys())
    n2 = len(response_sorted_keys)

    # Check for missing segments
    for index, key in enumerate(request_sorted_keys):
        l = len(request_buffer[key][1])
        if (index + 1 == n1):
            break
        next_seq = request_sorted_keys[index + 1]
        expected = next_seq - key
        if (expected != l):
            return None

    for index, key in enumerate(response_sorted_keys):
        l = len(response_buffer[key][1])
        if (index + 1 == n2):
            break
        next_seq = response_sorted_keys[index + 1]
        expected = next_seq - key
        if (expected != l):
            return None

    # Time Stamps for each payload
    request_payload = []
    request_timestamps = []
    for key in request_sorted_keys:
        request_timestamps.append(request_buffer[key][0])
        request_payload.append(request_buffer[key][1])

    response_payload = []
    response_timestamps = []
    for key in response_sorted_keys:
        response_timestamps.append(response_buffer[key][0])
        response_payload.append(response_buffer[key][1])

    req_delim_index = [request_payload.index(v) for v in request_payload if v.startswith(request)]
    res_delim_index = [response_payload.index(v) for v in response_payload if v.startswith(response)]

    if (len(req_delim_index) != len(res_delim_index)):
        stream_logger.info("Possible persistant connection, unable to match request/response pairs")
        return None
    # Time Stamps only for assembled packets, though kernel takes time of the order of nano seconds to assemble TCP payloads, we
    # consider timestamp of last TCP packet that is assembled
    http_req_timestamps = []
    http_res_timestamps = []
    #    req_timestamps=[i for i in request_timestamps if request_timestamps.index(i) in req_delim_index]
    #    res_timestamps = [i for i in response_timestamps if response_timestamps.index(i) in res_delim_index]

    # Invalid packet, is it possible?
    if (not req_delim_index or not res_delim_index):
        return None

    # Combine the payloads together to form complete requests
    for i in range(len(req_delim_index)):
        str = ""
        j = req_delim_index[i]
        if (j == len(request_payload) - 1):
            http_req_timestamps.append(request_timestamps[j])
            request_data.append(request_payload[j])
            break
        if j == req_delim_index[-1]:
            while (j < len(request_payload)):
                str = str + request_payload[j]
                j = j + 1
            http_req_timestamps.append(request_timestamps[j - 1])
            request_data.append(str)
            break

        while j < req_delim_index[i + 1]:
            str = str + request_payload[j]
            j = j + 1
        http_req_timestamps.append(request_timestamps[j - 1])
        request_data.append(str)

    # Combine the payloads together to form complete responses
    for i in range(len(res_delim_index)):
        str = ""
        j = res_delim_index[i]
        if (j == len(response_payload) - 1):
            http_res_timestamps.append(response_timestamps[j])
            response_data.append(response_payload[j])
            break
        if j == res_delim_index[-1]:
            while (j < len(response_payload)):
                str = str + response_payload[j]
                j = j + 1
            http_res_timestamps.append(response_timestamps[j - 1])
            response_data.append(str)
            break

        while j < res_delim_index[i + 1]:
            str = str + response_payload[j]
            j = j + 1
        http_res_timestamps.append(response_timestamps[j - 1])
        response_data.append(str)

    req_combined = zip(http_req_timestamps, request_data)
    res_combined = zip(http_res_timestamps, response_data)
    merged = req_combined + res_combined

    # As HTTP Responses are returned in FIFO, sorting by timestamp will make them ordered
    return sorted(merged, key=lambda x: x[0])


def parse_http(combined_data, key, tcp_id):
    """
    This function parses the combined HTTP packets
    :param combined_data: List of HTTP requests and responses
    :param key: Connection key
    :param tcp_id: Last TCP ID used as retrieved from the DB
    :return: Parsed HTTP list of tuples
    """
    if (key[0][-2:] == '80' and key[0][-3] == ':'):
        server, client = key[0], key[1]
    else:
        server, client = key[1], key[0]

    dump_list = []
    url = "NULL"
    host = "NULL"
    referer = "NULL"
    cnt = 0
    for ts, payload in combined_data:
        no_children = 0
        content_type = "NULL"
        cookies = "NULL"
        href_data = "NULL"
        iframe_data = "NULL"
        image_data = "NULL"
        cnt = cnt + 1
        if (cnt == 3):
            referer = "NULL"
        try:
            if (payload[:4] == 'HTTP'):  # Response
                source = server
                dest = client
                type = "Response"
                http = dpkt.http.Response(payload)
                headers = http.headers
                if (headers.has_key('content-type')):
                    content_type = headers['content-type']
                if (isinstance(content_type, list)):
                    # Sometimes multiple content type is present, we get the first as it will be always text if at all present
                    content_type = content_type[0]
                if (headers.has_key('set-cookie')):
                    cookies = headers['set-cookie']
                    if (isinstance(cookies, list)):  # More than 1 cookie is set
                        combined_cookies = ""
                        for cookie in cookies:
                            combined_cookies = combined_cookies + " && " + str(
                                cookie)  # Special delimiter to separate cookies later
                        cookies = combined_cookies
                if (headers.has_key('content-encoding')):
                    content_encoding = headers['content-encoding']
                    if (content_type.startswith(r'text/') and content_encoding == "gzip"):
                        output = StringIO(http.body)
                        gz = dpkt.gzip.Gzip(output.read())
                        try:
                            decoded_html = gz.decompress()
                            payload = decoded_html
                            if (content_type.startswith(r'text/html')):
                                http_util_ob = HttpUtil(payload, host)
                                no_children = http_util_ob.cnt
                                hrefs = http_util_ob.hrefs
                                iframes = http_util_ob.iframes
                                images = http_util_ob.images
                                if (http_util_ob.is_parent()):
                                    content_type = "html"
                                if (len(hrefs) > 0):
                                    href_data = ""
                                    for href in set(hrefs):
                                        href_data = href_data + " " + str(href)
                                if (len(iframes) > 0):
                                    iframe_data = ""
                                    for iframe in set(iframes):
                                        iframe_data = iframe_data + " " + str(iframe)
                                if (len(images) > 0):
                                    image_data = ""
                                    for image in set(images):
                                        image_data = image_data + " " + str(image).strip()

                        except Exception as e:
                            stream_logger.debug(e)

            else:  # Request
                source = client
                dest = server
                type = "Request"
                http = dpkt.http.Request(payload)
                headers = http.headers
                url = http.uri
                if headers.has_key('referer'):
                    referer = headers['referer']
                if headers.has_key('host'):
                    host = headers['host']
                    absolute_url = host + url
                if headers.has_key('cookie'):  # Clients cannot have more than one cookie
                    cookies = headers['cookie']

            if (host in settings.excluded_sites):
                continue
            dump_list.append((str(ts), 0, tcp_id, 0, source, dest, type, host, url, referer, cookies, content_type,
                              no_children, payload, href_data, iframe_data, image_data))

        except dpkt.UnpackError, e:
            stream_logger.info(str(e))

    return dump_list
