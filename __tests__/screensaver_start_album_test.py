# Simple tests to ensure XBMC mocks are working
import pytest
from unittest import mock
import sys
import os
from lib.screensaver import Screensaver, ADDON
import requests_mock
import time

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
        m.get("http://localhost:2283/api/albums/uuid1", json={"assets":[],"nextPage":False})
        
        grouping = screensaver._get_image_groupings()
        
    assert grouping == []
    
def test_image_groupings_use_album_next_page(screensaver):
    with requests_mock.Mocker() as m:
        m.get("http://localhost:2283/api/albums/uuid1", [{"json":{"assets":[]}},{"json":{"assets":{"items":[],"nextPage":False}}}])
        
        grouping = screensaver._get_image_groupings()
        
    assert grouping == []
    
    # {"id":"imageuuid1","originalPath":"/path/original/","originalMimeType":"image/jpeg","originalFileName":"imageuuid1.jpeg","localDateTime":"2012-01-01T23:12:34.56"}

def test_date_conversion_formats(screensaver):
    EXPECTED_TIME = time.strptime("2026-04-27T23:23:23", "%Y-%m-%dT%H:%M:%S")

    time1 = screensaver._parse_flexible_time("2026-04-27T23:23:23")
    time2 = screensaver._parse_flexible_time("2026-04-27T23:23:23.123")
    time3 = screensaver._parse_flexible_time("2026-04-27T23:23:23+123:")
    assert time1 == EXPECTED_TIME
    assert time2 == EXPECTED_TIME
    assert time3 == EXPECTED_TIME
