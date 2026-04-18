# Simple tests to ensure XBMC mocks are working
import pytest
from unittest import mock
import sys
import os
from lib.screensaver import Screensaver, ADDON
import requests_mock

@pytest.fixture(autouse=True)
def screensaver(mock_addon):
    addon_patcher = mock.patch.object(sys.modules['lib.screensaver'], 'ADDON', mock_addon)
    addon_patcher.start()
    mock_addon.getSettingBool = lambda x: {
        'useAlbum': True,
    }.get(x, False)
    screensaver = Screensaver() 
    screensaver._get_settings()
    return screensaver

def test_api_call(screensaver):
    """Test that basic api call returns data"""
    with requests_mock.Mocker() as m:
        m.get("http://localhost:2283/api/search/random", json={})
        
        response = screensaver._api_call("GET", "/api/search/random", {"size":1})
    
    assert response == {}

def test_image_groupings_use_album_empty_album(screensaver):
    with requests_mock.Mocker() as m:
        m.post("http://localhost:2283/api/search/metadata", json={"assets":{"items":[],"nextPage":False}})
        
        grouping = screensaver._get_image_groupings()
        
    assert grouping == []
    
def test_image_groupings_use_album_next_page(screensaver):
    with requests_mock.Mocker() as m:
        m.post("http://localhost:2283/api/search/metadata", [{"json":{"assets":{"items":[],"nextPage":True}}},{"json":{"assets":{"items":[],"nextPage":False}}}])
        
        grouping = screensaver._get_image_groupings()
        
    assert grouping == []
    