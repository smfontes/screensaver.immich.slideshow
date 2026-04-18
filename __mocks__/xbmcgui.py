# mocks/xbmcgui.py
import random

# Constants
WINDOW_FULLSCREEN_VIDEO = 10000
WINDOW_DIALOG_PROGRESS = 10020

class WindowXMLDialog:
    def __init__(self, *args, **kwargs):
        # In real Kodi, this loads the XML. Here we just init.
        self._closed = False
        self._controls = {}
        self._properties = {}
        
    def onInit(self):
        pass

    def onAction(self, action):
        pass

    def onClick(self, control_id):
        pass

    def onFocus(self, control_id):
        pass

    def onScroll(self, direction):
        pass

    def close(self):
        self._closed = True

    def getControl(self, control_id):
        if control_id not in self._controls:
            self._controls[control_id] = Control()
        return self._controls[control_id]

    def getProperty(self, key):
        return self._properties.get(key, "")

    def setProperty(self, key, value):
        self._properties[key] = str(value)

    def clearProperty(self, key):
        if key in self._properties:
            del self._properties[key]

    def getCurrentWindowDialogId(self):
        return 10000

    def getWidth(self):
        return 1920

    def getHeight(self):
        return 1080

class Window:
    def __init__(self, window_id):
        self._properties = {}
        
    def getProperty(self, key):
        return self._properties.get(key, "")

    def setProperty(self, key, value):
        self._properties[key] = str(value)

    def clearProperty(self, key):
        if key in self._properties:
            del self._properties[key]

class Control:
    def __init__(self):
        self._image = None
        self._animations = []

    def setImage(self, path, overlay=False):
        self._image = path

    def setAnimations(self, animations):
        self._animations = animations

class Dialog:
    def ok(self, heading, text):
        print(f"[DIALOG OK] {heading}: {text}")

    def yesno(self, heading, text):
        return True # Default to Yes for tests

class DialogProgress:
    def create(self, heading, line1="", line2="", line3=""):
        pass
    def update(self, percent, line1="", line2="", line3=""):
        pass
    def close(self):
        pass