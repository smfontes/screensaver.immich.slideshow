import os.path
import sys
import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon().getAddonInfo('name')

def log(msg, level=xbmc.LOGINFO):
    try:
        frame = sys._getframe(1)
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = frame.f_lineno
        xbmc.log(f"[{ADDON}] {filename}:{lineno} — {msg}", level)
    except Exception:
        xbmc.log(f"[{ADDON}] {msg}", level)

def notify(heading, message="", level=xbmcgui.NOTIFICATION_ERROR, ms=5000):
    xbmcgui.Dialog().notification(heading, message, level, time=ms)
