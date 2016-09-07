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
import shlex
import threading
import time
import queryprocessor
import critter_settings
from kivy.adapters.listadapter import ListAdapter
from subprocess import Popen
from sys import platform as _platform
from kivy.app import App
from kivy.config import Config
from kivy.lang import Builder
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.listview import ListItemButton
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from critter_settings import settings
from driver import Driver
from http import buildsession_worker
from kivy_settings import Settings

if _platform == "win32":
    import win32api

FILE_SIZE = 100
NO_FILES = 5

from queryprocessor import queryprocessor_worker

Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '500')

Builder.load_string('''
#:import ListAdapter kivy.adapters.listadapter.ListAdapter
#:import ListItemButton kivy.uix.listview.ListItemButton

<ListItemButton>:
    selected_color: 0, 0, 1, 1
    deselected_color: 0, 1, 0, 1
<Home>:

    site_list: site_list_view
    BoxLayout:
        id: home_layout
        orientation: 'vertical'
        padding: [5,5,5,5]
        spacing: 10

        Label:
            text: 'Critter@Home Client'
            font_size: 32


        BoxLayout:
            orientation: 'vertical'

            Label:
                text: 'Any websites whose traffic we should never record?'
                font_size: 15
                halign: 'left'
                text_size: self.size


        ListView:
            id: site_list_view
            adapter:
                ListAdapter(data=["example.com"],cls=ListItemButton)

        BoxLayout:
            size_hint_y: None
            height: "25dp"

            TextInput:
                id: site_input
                size_hint_x: 30
            Button:
                text: "Add"
                size_hint_x: 15
                on_press: root.add_site(site_input.text)
            Button:
                text: "Delete"
                size_hint_x: 15
                on_press: root.del_site()

        BoxLayout:
            orientation: 'vertical'
            Label:
                text_size: self.size
                text: 'Only include my data in computations when there are more than \\'k\\' users with behavior similar to mine. Specify \\'k\\':'
                halign: 'left'
                font_size: 15

            TextInput:
                id: k_value
                multiline:False
                write_tab: False
                size_hint_y: 0.5

        BoxLayout:
            orientation: 'horizontal'

            Button:
                text: "Save"
                font_size: 24
                size_hint: (.4, .6)
                on_press: root.save(k_value.text)

            Button:
                id: start_stop
                text: 'Start'
                font_size:24
                size_hint: (.4, .6)
                on_press: root.start_client()

''')


# This class creates instances of a thread which can be stopped. The 'target' function is run every 'timeout' seconds until the thread is stopped
class StoppableThread(threading.Thread):
    def __init__(self, target, timeout):
        super(StoppableThread, self).__init__()
        self._target = target
        self._timeout = timeout
        self._stop = threading.Event()

    def run(self):
        while (not self._stop.isSet()):
            self._stop.wait(self._timeout)
            if self._stop.isSet():
                continue;
            self._target()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

class Home(Screen, Settings):
    def __init__(self, *args, **kwargs):
        super(Screen, self).__init__(*args, **kwargs)
        self.cc = None
        self.qp = None
        self.sb = None
        self.pid = None
        self.process = None
        updater_thread = threading.Thread(target=self.check_updates)
        updater_thread.setDaemon(True)

    def start_client(self):
        if (self.ids.start_stop.text == 'Stop'):
            self.ids.start_stop.text = 'Start'
            self.stop_client()
            return

        self.ids.start_stop.text = 'Stop'
        self.qp = StoppableThread(queryprocessor_worker, critter_settings.FETCH_SLEEP_TIMEOUT)
        self.qp.setDaemon(True)
        self.sb = StoppableThread(buildsession_worker, critter_settings.DB_LINKER_TIMEOUT)
        self.sb.setDaemon(True)

        if (_platform == "darwin"):
            command = "sudo tcpdump -i any -w " + critter_settings.USER_DIR+ "/cap.pcap -C " + str(FILE_SIZE) + " -W " + str(NO_FILES) + " tcp port http"
        elif _platform == "linux" or _platform == "linux2":
            command = "sudo tcpdump -i any -w " + critter_settings.USER_DIR+ "/cap.pcap -C " + str(FILE_SIZE) + " -W " + str(NO_FILES) + " tcp port http"
        elif _platform == "win32":
            command = "windump -i 1 -w " + '"'+critter_settings.USER_DIR+ "\\cap.pcap" +'" '+ "-C " + str(FILE_SIZE) + " -W " + str(NO_FILES) + " tcp port http"
        self.process = Popen(shlex.split(command), shell=False)  # Use this and not shell=True
        self.pid = self.process.pid

        # Decrypt DB
        critter_settings.settings.decrypt_db()

        # Run driver thread in background
        self.cc = Driver()
        self.cc.setDaemon(True)
        self.cc.start()

        # Run query processor thread in background
        self.qp.start()

        # Run sessions builder thread in background
        self.sb.start()

    def stop_threads(self):
        self.cc.stop()
        self.qp.stop()
        self.sb.stop()
        self.cc.join()
        self.qp.join()
        self.sb.join()

    def stop_client(self):

        if _platform == "darwin":
            if self.pid is None:
                pass
            else:
                os.system("sudo kill %s" % (self.pid,))
                os.wait()
                self.pid = None

        elif _platform == "win32":
            if self.process is None:
                pass
            else:
                self.process.terminate()
                self.process = None

        # Encrypt DB
        critter_settings.settings.encrypt_db()

        # sys.stderr.write("Stopped Successfully")
        print "Stopped Successfully"

    def stop_app(self):

        if _platform == "darwin":
            if self.pid is not None:  # Won't enter if the application is opened then closed without starting
                self.stop_client()
        elif _platform == "win32":
            if self.process is not None:  # Won't enter if the application is opened then closed without starting
                self.stop_client()
        App.get_running_app().stop()


    def update(self):
        if _platform == "darwin":
            os.system(
                'open autoupdate-osx.app --args --mode unattended --unattendedmodebehavior download --unattendedmodeui minimalWithDialogs')
        if _platform == "win32":
            win32api.ShellExecute(0, 'open', 'autoupdate-windows.exe',
                                  '--mode unattended --unattendedmodebehavior download --unattendedmodeui minimalWithDialogs',
                                  '', 0)
        self.stop_app()

    def check_updates(self):
        while True:
            status = None
            if _platform == "darwin":
                status = os.system('open autoupdate-osx.app --args --mode unattended')
            elif _platform == "win32":
                status = os.system('open autoupdate-windows.exe --args --mode unattended')
            if status == 0:
                box = BoxLayout(orientation='vertical')
                box.add_widget(
                    Label(text='An update is available for download. Would you like to download and install it?'))
                b = Button(text='Yes')
                box.add_widget(b)
                b2 = Button(text='No')
                box.add_widget(b2)
                popup = Popup(title='Update', content=box, size_hint=(None, None), size=(200, 200), auto_dismiss=False)
                b2.bind(on_press=popup.dismiss)
                b.bind(on_press=self.update())
                popup.open()

            time.sleep(critter_settings.UPDATE_CHECK_TIMEOUT)




class CritterClient(App):
    home = Home(name='home')

    def build(self):
        manager = ScreenManager()
        manager.add_widget(self.home)
        #manager.add_widget(Settings(name='settings'))
        return manager

    def on_stop(self):
        self.home.stop_client()


if __name__ == '__main__':
    CritterClient().run()
