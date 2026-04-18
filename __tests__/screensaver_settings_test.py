# Simple tests to ensure XBMC mocks are working
import pytest
from unittest import mock
import sys
import os
from lib.screensaver import Screensaver, ADDON

@pytest.fixture(autouse=True)
def screensaver(mock_addon):
    addon_patcher = mock.patch.object(sys.modules['lib.screensaver'], 'ADDON', mock_addon)
    addon_patcher.start()
    screensaver = Screensaver() 
    return screensaver

def test_basic_settings_are_set(screensaver):
    """Test that basic settings are correctly assigned"""
    screensaver._get_settings()
    
    assert screensaver.slideshow_URL == 'http://localhost:2283'
    assert screensaver.slideshow_APIKey == 'test-key'

# TODO Immich API doesn't accept multiple UUIDs - returns to empty JSONs so should change this to only accept first UUID
def test_album_uuid_is_split_into_list(screensaver):
    """Test that comma-separated album UUIDs are converted to list"""
    screensaver._get_settings()
    
    expected = ['uuid1', 'uuid2', 'uuid3']
    assert screensaver.slideshow_AlbumUUID == expected

def test_album_uuid_empty_string_becomes_None(mock_addon, screensaver):
    mock_addon.getSetting = lambda x: {
        'albumUUID': '',
    }.get(x, '')
    
    screensaver._get_settings()
    
    assert screensaver.slideshow_AlbumUUID == None

def test_integer_settings_are_converted(screensaver):
    screensaver._get_settings()
    
    assert screensaver.slideshow_time == 5
    assert screensaver.slideshow_limit == 10
    assert screensaver.slideshow_dbport == 5432

def test_boolean_settings_are_converted(screensaver):
    screensaver._get_settings()
    
    assert not screensaver.slideshow_useAlbum
    assert screensaver.slideshow_date
    assert screensaver.slideshow_tags
    assert not screensaver.slideshow_music
    assert screensaver.slideshow_clock
    assert screensaver.slideshow_burst
    assert screensaver.slideshow_panorama
    assert not screensaver.slideshow_kenburns
    assert not screensaver.slideshow_dbdates

def test_dim_value_conversion_to_hex(screensaver):
    screensaver._get_settings()
    
    assert screensaver.slideshow_dim.startswith('7f')
    assert screensaver.slideshow_dim.endswith('ffffff')

def test_dim_value_edge_cases(mock_addon, screensaver):
    mock_addon.getSettingInt = lambda x: {
        'level': 0,
    }.get(x, 50)
    
    screensaver._get_settings()
    assert screensaver.slideshow_dim == '0ffffff'
    
    mock_addon.getSettingInt = lambda x: {
        'level': 100,
    }.get(x, 50)
    
    screensaver._get_settings()
    assert screensaver.slideshow_dim == 'ffffffff'


