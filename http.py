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
import time
from collections import namedtuple

from bs4 import BeautifulSoup

import critter_settings
from critter_settings import PAGE_LOAD_TIMEOUT, BROWSING_SESSION_TIMEOUT

#A single page id is assigned to the parent and their children recursively
global page_id
page_id = 0

#Image file types to link with parent page
image_formats = ('.bmp', '.gif', '.jpeg', '.jfif', '.jpg', '.png', '.ppm', '.pgm', '.pbm', '.pnm', '.tiff')

class BuildSession:
    def __init__(self):
        self.sql = critter_settings.init()
        self.sql.update_query("""UPDATE ParsedHTTP SET browsing_session_id = %s, page_id = %s""",
                              [(0, 0)])  # Initialise the table with 0s

    def process_table(self):
        """
        This function processes the packet table by linking the rows together with ids
        :return: None
        """
        httptuple = namedtuple('httptuple',
                               ['id', 'timestamp', 'page_id', 'tcp_id', 'browsing_session_id', 'type', 'host', 'url',
                                'referer', 'content_type', 'payload', 'hrefs', 'iframes', 'images'])
        treetuple = namedtuple('tree', ['tcp_id', 'browsing_id', 'host', 'url', 'no_children'])

        timestamp_marker = 0
        while True:

            res = self.sql.request_query("""SELECT no,  timestmp, page_id, tcp_session_id, browsing_session_id, http_type, host,
                                url, referer, content_type, payload, hrefs, iframes, images  FROM ParsedHTTP where content_type LIKE %s and timestmp > %s ORDER BY
                                 timestmp, tcp_session_id LIMIT 1""", ("html", timestamp_marker))

            if (res is None):
                return
            if (len(res) == 0):
                return
            row = res[0]

            ht = httptuple(*row)
            timestamp_marker = ht.timestamp

            if (ht.browsing_session_id == 0):
                browsing_id = ht.id
            else:
                browsing_id = ht.browsing_session_id

            absolute_url = "http://" + ht.host + ht.url

            href_set = set(ht.hrefs.split(" "))
            iframe_set = set(ht.iframes.split(" "))
            image_set = set(ht.images.split(" "))
            res = self.sql.request_query(
                """SELECT tcp_session_id, browsing_session_id, host, url, no_children FROM ParsedHTTP WHERE (referer = %s OR referer = %s) AND timestmp BETWEEN %s AND %s""",
                (absolute_url, "https://www.google.com/", float(ht.timestamp),
                 float(ht.timestamp) + BROWSING_SESSION_TIMEOUT))

            to_update = []
            to_update.append((browsing_id, ht.tcp_id))

            # Link html/text parents and their a href/iframe children with browsing session id
            for row in res:
                tree = treetuple(*row)
                abs_url = get_abs_url(tree.host, tree.url)
                if (tree.browsing_id != 0):
                    if ((browsing_id in to_update)):
                        to_update.remove((browsing_id,
                                          ht.tcp_id))  # If children of a particular parent are found to belong to another parent, then this parent is also a child of previous parent
                        to_update.append((tree.browsing_id, ht.tcp_id))
                if ((abs_url in href_set) or (abs_url in iframe_set) or (abs_url in image_set) or abs_url.endswith(
                        image_formats)):
                    to_update.append((browsing_id, tree.tcp_id))

            self.sql.update_query("""UPDATE ParsedHTTP SET browsing_session_id = %s WHERE tcp_session_id = %s""",
                                  to_update)

            # Link html/text parents and their iframe/img children with page id
            res = self.sql.request_query(
                """SELECT no, page_id, tcp_session_id, host, url FROM ParsedHTTP WHERE referer = %s AND timestmp BETWEEN %s AND %s""",
                (absolute_url, float(ht.timestamp), float(ht.timestamp) + PAGE_LOAD_TIMEOUT))
            if (len(res) == 0):
                return
            if (ht.page_id == 0):
                page_id = page_id + 1
                to_update_page_ob = self.build_page(page_id, res, iframe_set, image_set)
                to_update_page_ob.append((page_id, ht.id))
            else:
                to_update_page_ob = self.build_page(ht.page_id, res, iframe_set, image_set)

            self.sql.update_query("""UPDATE ParsedHTTP SET page_id = %s WHERE no = %s""", to_update_page_ob)

    def build_page(self, parent_page_id, fetched_rows, iframe_set, image_set):
        """
        This function links the pages together based on iframes and images.
        :param parent_page_id: The page id of root
        :param fetched_rows: list of tuples returned on query
        :param iframe_set: Set of iframes
        :param image_set: Set of images
        :return: ids to update
        """
        to_update = []
        for row in fetched_rows:
            abs_url = get_abs_url(row[3], row[4])
            if (abs_url in iframe_set or abs_url in image_set or abs_url.endswith(image_formats)):
                if (row[1] == 0):
                    to_update.append((parent_page_id, row[0]))
                else:  # iframes/images belong to some previous parent
                    continue

        return to_update


class HttpObject:
    def __init__(self, id, timestamp, tcp_id, browsing_session_id, type, host, url, referer, content_type):
        self.id = id
        self.timestamp = timestamp
        self.tcp_id = tcp_id
        self.browsing_session_id = browsing_session_id
        self.type = type
        self.host = host
        self.url = url
        self.referer = referer
        self.content_type = content_type
        self.href_dict = {}


class HttpUtil:
    """
    Functions in this class parse HTTP request/response data using BeautifulSoup module
    """
    def __init__(self, payload, host):
        self.soup = BeautifulSoup(payload, "html.parser")
        self.host = host
        self.hrefs = self.parse_href()
        self.iframes = self.parse_iframe()
        self.cnt = 0
        self.images = self.parse_img()

    def parse_href(self):
        """
        This function parses the hrefs from BeautifulSoup object
        :return: list of hrefs
        """
        children = []

        for a in self.soup.find_all('a'):
            url = str(a.get('href'))
            if (url.startswith("#") or url.startswith("https") or url.startswith(
                    "javascript:void(0)")):  # Skip javascript scrolling and secure links
                continue
            children.append(get_abs_url(self.host, url))

        return children

    def parse_iframe(self):
        """
        This function parses the iframes from BeautifulSoup object
        :return: list of iframes
        """
        iframes = []
        for iframe in self.soup.find_all('iframe'):
            url = str(iframe.get('src'))
            if (url.startswith("https")):
                continue
            if (url != "None" and url != ""):
                iframes.append(get_abs_url(self.host, url))

        return iframes

    def parse_img(self):
        """
        This function parses the images from BeautifulSoup object
        :return: list of images
        """
        images = []
        cnt = 0
        for image in self.soup.find_all('img'):
            url = str(image.get('src'))
            if (url.startswith("https")):
                continue
            if (url != "None" and url != ""):
                images.append(get_abs_url(self.host, url))
            cnt += 1
        self.cnt = cnt
        return images

    def count_img(self):
        """
        This function counts the number of images from BeautifulSoup object
        :return: count of images
        """
        cnt = 0
        for image in self.soup.find_all('img'):
            url = image.get('src')
            cnt += 1
        return cnt

    def is_parent(self):
        l = self.soup.find('html')
        if (l):
            return True


def get_abs_url(host, url):
    """
    Utility function to get absolute URL from generic URLs
    :param host: domain name
    :param url: domain directory
    :return: absolute url of the form http://www.example.com
    """
    res = ""
    if (url.startswith("http")):
        res = url
    elif (url.startswith("//")):  # For protocol dependendent URLs make them http
        res = "http:" + url
    elif (not url.startswith("/")):
        res = "http://" + host + "/" + url
    else:
        res = "http://" + host + url

    return res.replace("com?", "com/?", 1)


def buildsession_worker():
    session = BuildSession()
    session.process_table()
