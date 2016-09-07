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
import base64
import os
import urlparse

import pyaes
import random
import string
from os.path import expanduser

import requests

FILE_SIZE = 100
NO_FILES = 5
SLEEP_INTERVAL = 10
USER_DIR = expanduser("~/.critter")
FETCH_SLEEP_TIMEOUT = 200
DB_LINKER_TIMEOUT = 200
K_ANON_VALUE = 2
MAX_RECORDS_RETRIEVE = 1000
BROWSING_SESSION_TIMEOUT = 300
PAGE_LOAD_TIMEOUT = 15
QUERY_RUN_FREQUENCY = 3600
UPDATE_CHECK_TIMEOUT = 86400

if(not os.path.exists(USER_DIR)):
    os.makedirs(USER_DIR)

class Settings:
    """
    This class contains the settings
    """
    def __init__(self):
        self.server_addr = "https://steel.isi.edu/critter/"
        self.key = ""
        self.k_value = 1
        self.query_history_file_name = USER_DIR + "/history"
        self.excluded_sites = []

        if (not os.path.isfile(USER_DIR+"/settings")):
            f = open(USER_DIR+"/settings",'w')
            self.username = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(16))
            self.password = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(16))
            res = register(self.username, self.password)
            if res['isSuccessfull']:
                f.write(self.username + "\n")
                f.write(self.password + "\n")
                f.write(str(self.k_value) + "\n")
            else:
                print res['errorMessage']
                f.close()
                os.remove(USER_DIR+"/settings")
        else:
            with open(USER_DIR+"/settings",'r') as f:
                lines=f.readlines()
                self.username = lines[0].strip()
                self.password = lines[1].strip()
                self.k_value = lines[2].strip()

        if (not os.path.isfile(USER_DIR+"/rand")):
            f = open(USER_DIR+"/rand", 'w')
            rand = os.urandom(32)
            self.key = str(rand)
            f.write(base64.b64encode(str(rand)))
            f.close()
        else:
            f = open(USER_DIR+"/rand", 'r')
            self.key = base64.b64decode(f.readline())
            f.close()

    def encrypt_db(self):
        mode = pyaes.AESModeOfOperationCTR(self.key)
        if (os.path.isfile(USER_DIR+'/critter.db')):
            file_in = open(USER_DIR+'/critter.db', 'rb')
            file_out = open(USER_DIR+'/critter_enc.db', 'wb')
            pyaes.encrypt_stream(mode, file_in, file_out)
            file_in.close()
            file_out.close()
            os.remove(USER_DIR+'/critter.db')

    def decrypt_db(self):
        mode = pyaes.AESModeOfOperationCTR(self.key)
        if (os.path.isfile(USER_DIR+'/critter_enc.db')):
            file_in = open(USER_DIR+'/critter_enc.db', 'rb')
            file_out = open(USER_DIR+'/critter.db', 'wb')
            pyaes.decrypt_stream(mode, file_in, file_out)
            file_in.close()
            file_out.close()
            os.remove(USER_DIR+'/critter_enc.db')

def register(username, password):
    """
    This function registers a Critter client user with supplied username and password on steel.isi.edu/critter/register.php
    :return:
    """
    payload = {'user': username, 'password': password}
    try:

        register_url = urlparse.urljoin("https://steel.isi.edu/critter/", "registerbackend.php")
        r = requests.post(register_url, data=payload)
        if "Successfully Registered" in r.text:
            return {'isSuccessfull': True, 'cookies': r.cookies, 'errorMessage': '',
                    'serverResponse': ''}
        elif "already exists" in r.text:
            return {'isSuccessfull': False, 'cookies': None,
                    'errorMessage': 'Username already exists',
                    'serverResponse': ''}
        else:
            return {'isSuccessfull': False, 'cookies': None,
                    'errorMessage': 'Unknown Error in register',
                    'serverResponse': r.text}
    except requests.exceptions.RequestException:
        return {'isSuccessfull': False, 'cookies': None,
                'errorMessage': 'Connect To Critter Server Failed',
                'serverResponse': 'requestException'}


#This is a global object initialised once
global settings
settings = Settings()

from sqlitedb import SQLite


def init():
    # sql = mysqldb.MySQL()
    sql = SQLite()
    return sql
