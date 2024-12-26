import xbmcaddon

from lib import screensaver

CWD = xbmcaddon.Addon().getAddonInfo('path')

if __name__ == '__main__':
    screensaver_window = screensaver.Screensaver('screensaver.immich.slideshow.xml', CWD, 'default')
    screensaver_window.doModal()
    del screensaver_window
