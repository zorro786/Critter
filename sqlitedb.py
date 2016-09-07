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
import sqlite3
from critter_settings import USER_DIR
db_logger = logging.getLogger("DBLogger")
db_logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
db_logger.addHandler(ch)


class SQLite:
    """
    This class takes care of SQLite operations. Below two are class variables.
    """
    connection = None
    cursor = None

    def __init__(self):
        conn = sqlite3.connect(
            database=USER_DIR+r'/critter.db')
        conn.text_factory = str  # Required because default encoding expects Unicode
        cursor = conn.cursor()
        parsed_http = """CREATE TABLE IF NOT EXISTS ParsedHTTP(
                        no integer PRIMARY KEY,
                        timestmp text NOT NULL,
                        page_id integer NOT NULL,
                        tcp_session_id  integer NOT NULL,
                        browsing_session_id integer,
                        source text NOT NULL,
                        dest text NOT NULL,
                        http_type text NOT NULL,
                        host text,
                        url text,
                        referer text,
                        cookie text,
                        content_type text,
                        no_children integer,
                        payload text NOT NULL,
                        hrefs text NOT NULL,
                        iframes text NOT NULL,
                        images text NOT NULL
                        )"""

        # cursor.execute(captures)
        #        cursor.execute("PRAGMA key = '%s'" % settings.key)
        cursor.execute(parsed_http)
        conn.commit()
        cursor.close()
        conn.close()

    def connect(self):
        cnx = sqlite3.connect(
            database=USER_DIR+r'/critter.db')
        cnx.text_factory = str
        return cnx

    def insert_query(self, dump):
        """
        This is a wrapper function to run INSERT queries in to the table
        :param dump: Single tuple of data
        :return: None
        """
        try:
            if (self.connection is None):
                self.connection = self.connect()

            self.cursor = self.connection.cursor()
            #            self.cursor.execute("PRAGMA key = '%s'" % settings.key)
            self.cursor.execute("""
                        INSERT INTO ParsedHTTP (timestmp, page_id, tcp_session_id, browsing_session_id, source, dest, http_type,
                        host, url, referer, cookie, content_type, no_children, payload, hrefs, iframes, images)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", dump)
            self.connection.commit()

        except sqlite3.Error as e:
            try:
                self.connection = self.connect()
                self.cursor = self.connection.cursor()
                self.cursor.execute("""
                            INSERT INTO ParsedHTTP (timestmp, page_id, tcp_session_id, browsing_session_id, source, dest, http_type,
                            host, url, referer, cookie, content_type, no_children, payload, hrefs, iframes, images)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", dump)
                self.connection.commit()
            except sqlite3.OperationalError as e:
                db_logger.debug(str(e) + " : " + dump)

    def request_query(self, query, data):
        """
        This is a wrapper function to run queries that return data. Currently only those that have SELECT function.
        :param query: SQL query
        :param data: Parameters for the query if any
        :return: Fetched rows from table
        """
        res = None
        try:
            if (self.connection is None):
                self.connection = self.connect()
            self.cursor = self.connection.cursor()
            if data == None:
                self.cursor.execute(query)
            else:
                self.cursor.execute(query, data)
            res = self.cursor.fetchall()

        except sqlite3.Error as e:
            db_logger.debug(str(e))

        return res

    def update_query(self, query, data):
        """
        This is a wrapper function to run UPDATE query without returning any data from the table. Can merge this with the function above if required.
        :param query: SQL query
        :param data: Paremeters for the query if any
        :return: N/A
        """
        try:
            if (self.connection is None):
                self.connection = self.connect()
            self.cursor = self.connection.cursor()
            self.cursor.executemany(query, data)
            self.connection.commit()
        except sqlite3.Error as e:
            db_logger.debug(str(e) + " : " + str(data))

    def get_last_session_ids(self):
        """
        This function returns the last IDs used in table. Currently it returns last TCP id.
        :return: Last TCP id used in DB Table.
        """
        # ids = {'tcp_id' : None , 'parent_id' : None}
        tcp_id = None
        query1 = "SELECT tcp_session_id FROM ParsedHTTP ORDER BY no DESC LIMIT 1;"
        # query2 = "SELECT TOP 1 parent_id FROM ParsedHTTP WHERE parent_id IS NOT NULL ORDER BY no DESC"
        try:
            if (self.connection is None):
                self.connection = self.connect()
            self.cursor = self.connection.cursor()
            self.cursor.execute(query1)
            temp = self.cursor.fetchone()
            if (temp == None):
                tcp_id = 0
            else:
                tcp_id = temp[0]
                # self.cursor.execute(query2)
                # if(self.cursor.rowcount == 0):
                #    ids['parent_id'] = 0
                # else:
                #    ids['parent_id'] = self.cursor.fetchone()[0]
        except sqlite3.Error as e:
            db_logger.debug(e)
        else:
            return tcp_id
        return None

