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

from kivy.adapters.listadapter import ListAdapter
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.listview import ListItemButton
from kivy.uix.popup import Popup

import queryprocessor
from critter_settings import settings, USER_DIR

class Settings():
    site_list = ObjectProperty(None)

    def __init__(self):

        if (os.path.isfile("settings")):
            with open("settings", "r") as f:
                lines = f.readlines()
                if (len(lines) >= 3):
                    settings.username = lines[0].strip()
                    settings.password = lines[1].strip()
                    settings.k_value = lines[2].strip()
                    for i in range(3, len(lines)):
                        settings.excluded_sites.append(lines[i].strip())

        if (len(settings.excluded_sites) > 0):
            self.site_list.adapter = ListAdapter(data=settings.excluded_sites, cls=ListItemButton)

    def add_site(self, site):
        self.site_list.adapter.data.extend([site])
        self.site_list._trigger_reset_populate()

    def del_site(self, *args):
        if self.site_list.adapter.selection:
            selection = self.site_list.adapter.selection[0].text
            self.site_list.adapter.data.remove(selection)
            self.site_list._trigger_reset_populate()

    def is_int(self, s):
        try:
            int(s)
            if int(s)>0:
                return True
            else:
                return False
        except ValueError:
            return False

    def save(self, k_value):

        #settings.username = username
        #settings.password = password
        settings.k_value = k_value


        if k_value != "" and self.is_int(k_value):
            res = queryprocessor.update_k_value()
            if not res['isSuccessfull']:
                box = BoxLayout(orientation="vertical")
                box.add_widget(Label(text=res['errorMessage'], font_size=14))
                b = Button(text='OK', size_hint = (1,0.5))
                box.add_widget(b)
                popup = Popup(title='Error', content=box, size_hint=(None, None), size=(300, 150), auto_dismiss=False, font_size = 16)
                b.bind(on_press=popup.dismiss)
                popup.open()
                return
        else:
            box = BoxLayout(orientation="vertical")
            box.add_widget(Label(text='Only integer K value >= 1 is allowed', font_size=14))
            b = Button(text='OK', size_hint = (1,0.5))
            box.add_widget(b)
            popup = Popup(title='Error', content=box, size_hint=(None, None), size=(300, 150), auto_dismiss=False, font_size = 16)
            b.bind(on_press=popup.dismiss)
            popup.open()
            return

        f = open(USER_DIR + r"/settings", "r")
        lines = f.readlines()
        settings.k_value = k_value
        f.close()
        f = open(USER_DIR + r"/settings", "w")
        f.write(lines[0])
        f.write(lines[1])
        f.write(k_value + "\n")

        for i in range(0, len(self.site_list.adapter.data)):
            item = self.site_list.adapter.get_data_item(i)
            f.write(item + "\n")
        f.close()
        box = BoxLayout(orientation='vertical')
        box.add_widget(Label(text='Settings Saved', font_size=14))
        # create content and add to the popup
        b = Button(text='OK', size_hint = (1,0.5))
        box.add_widget(b)
        popup = Popup(title='Info', content=box, size_hint=(None, None), size=(300, 150), auto_dismiss=False, font_size = 16)

        # bind the on_press event of the button to the dismiss function
        b.bind(on_press=popup.dismiss)

        # open the popup
        popup.open()

    def do_login(self, username, password):

        settings.username = username
        settings.password = password
        login_result = queryprocessor.login()

        if (login_result['isSuccessfull']):

            box = BoxLayout(orientation='vertical')
            box.add_widget(Label(text='Login Successfull', font_size=14))
            # create content and add to the popup
            b = Button(text='OK', size_hint = (1,0.5))
            box.add_widget(b)
            popup = Popup(title='Info', content=box, size_hint=(None, None), size=(300, 150), auto_dismiss=False, font_size = 16)

            # bind the on_press event of the button to the dismiss function
            b.bind(on_press=popup.dismiss)

            # open the popup
            popup.open()
        else:

            box = BoxLayout(orientation='vertical')
            box.add_widget(Label(text='Incorrect Username/Password'))
            b = Button(text='OK', size_hint = (1,0.5))
            box.add_widget(b)

            # create content and add to the popup
            popup = Popup(title='Error', content=box, size_hint=(None, None), size=(300, 150), auto_dismiss=False, font_size = 16)

            # bind the on_press event of the button to the dismiss function
            b.bind(on_press=popup.dismiss)

            # open the popup
            popup.open()
