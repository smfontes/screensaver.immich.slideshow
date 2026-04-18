import os

class Addon:
    def __init__(self, addon_id=None):
        self.id = addon_id or "screensaver.immich.slideshow"
        self._settings = {}

    def getAddonInfo(self, key):
        if key == 'id':
            return self.id
        if key == 'path':
            return os.getcwd()
        if key == 'profile':
            return os.path.expanduser("~/.kodi/userdata/addon_data/" + self.id)
        return ""

    def getSetting(self, key):
        defaults = {
            'URL': 'http://localhost:2283',
            'APIKey': 'test-key',
            'albumUUID': 'uuid1,uuid2,uuid3',
            'dbhost': 'localhost',
            'dbname': 'immich_db',
            'dbuser': 'immich_user',
            'dbpassword': 'secret_password',
        }
        return self._settings.get(key, defaults.get(key, ""))

    def getSettingInt(self, key):
        defaults = {
            'time': 5,
            'limit': 10,
            'level': 50,
            'dbport': 5432,
        }
        return self._settings.get(key, defaults.get(key, 0))

    def getSettingBool(self, key):
        defaults = {
            'date': True,
            'tags': True,
            'music': False,
            'clock': True,
            'burst': True,
            'panorama': True,
            'kenburns': False,
            'dbdates': False,
        }
        return self._settings.get(key, defaults.get(key, False))

    def getLocalizedString(self, id):
        # Map string IDs to "String_ID"
        return f"String_{id}"