import sys
import unittest
from unittest import mock
import pytest
from __mocks__.xbmcaddon import Addon
from __mocks__.xbmcgui import WindowXMLDialog, Control

@pytest.fixture
def mock_addon():
    return Addon()

sys.modules['xbmc'] = mock.MagicMock()
sys.modules['xbmcgui'] = mock.MagicMock()
sys.modules['xbmcgui'].WindowXMLDialog = WindowXMLDialog
sys.modules['xbmcgui'].Window = mock.MagicMock()
sys.modules['xbmcgui'].Control = Control
sys.modules['xbmcgui'].Dialog = mock.MagicMock()
sys.modules['xbmcgui'].DialogProgress = mock.MagicMock()

sys.modules['xbmcvfs'] = mock.MagicMock()
sys.modules['xbmcvfs'].translatePath = lambda p: p.replace("special://profile/", "/tmp/")
sys.modules['pg8000'] = mock.MagicMock()
sys.modules['pg8000.dbapi'] = mock.MagicMock()
sys.modules['iptcinfo3'] = mock.MagicMock()
sys.modules['imagesize'] = mock.MagicMock()
sys.modules['xbmcaddon'] = mock.MagicMock()
sys.modules['xbmcaddon'].Addon = Addon