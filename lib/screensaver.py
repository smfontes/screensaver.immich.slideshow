# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with Kodi; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html

## Screensaver that displays a slideshow of pictures grouped by the date the pictures were created.

#  This Program uses the immich api to retrieve images from immich.
#  Pictures are selected from immich that were all taken on the same date.
#  A group of pictures from that date are displayed.
#  Another date is chosen, and another group of pictures are displayed, etc.

### Additional features:

#     1. Some information from each picture can be displayed by the screensaver.
#        - Image tags if they occur in the immich database or in the image file itself
#          - Album Name
#          - Headline
#          - Caption
#          - Sublocation, City, State/Province, Country
#        - The image date and time
#     2. The current time can be displayed on each slide.
#     3. If pictures are taken in "burst mode" with a camera, then you may have
#        dozens of pictures, with multiple occuring in the same second, that look
#        almost identical. This makes for a very boring slideshow if each slide is
#        shown for a few seconds. When there are many pictures taken very close
#        together in time, you can selkect to have the slideshow speed up so that
#        there is much less time between "burst mode" images.
#     4. If music is playing when the slideshow is running, information about the
#        currently playing music can be displayed.
#     5. Slides can be displayed dimmed.
#     6. For panoramic slides, there is the option to pan across the slide from end
#        to end, rather than showing the entire slide.
#     7. There is the option to turn on "Ken Burns" mode for slides
#     8. There is the option to only display images that are marked as a favorite in
#        immich (by the user that the API key belongs to). If no images are marked
#        as favorites, the option is ignored.
#     9. There is the option to only show slides from selected albums.
#    10. There is the option to use preview for image types that are not compatible 
#        with Kodi. This uses Immich's previews (jpegs) to display the images.
#    11. There is the option to randomly choose from a list of unique picture dates,
#        rather than choosing a random picture to get a date for the image group.
#        This allows each date to be chosen with the same probability, rather than
#        dates with more pictures being chosen more frequently. Requires you to set
#        up direct access to the immich database.

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import os
import sys
import random
import time
import json
from datetime import datetime
from pathlib import Path
from iptcinfo3 import IPTCInfo
# Turn off all the warnings from IPTCInfo
import logging
logging.getLogger("iptcinfo").setLevel(logging.ERROR)
sys.path.insert(0, os.path.join(sys.path[0], 'modules'))
import imagesize

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'lib'))
from services import ImmichAPI
from services import DatabaseAPI
from services import log, notify

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_USERDATA_FOLDER = Path(xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}"))
IMMICH_TEMP_FILE_EXTENSION = '.immich-tmp'
ALBUMS_FILE = ADDON_USERDATA_FOLDER / "selected_albums.json"

# Formats that can be displayed in a slideshow
PICTURE_FORMATS = ('bmp', 'jpeg', 'jpg', 'gif', 'png', 'tiff', 'mng', 'ico', 'pcx', 'tga', 'heic', 'heif')
MAX_CONSECUTIVE_EMPTY_DATES = 25
EXCEPTION_TYPE_NOT_HANDLED = 30940

class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        pass

    def onInit(self):
        try:
            # Init the monitor class to catch onscreensaverdeactivated calls
            self.Monitor = MyMonitor(action = self._exit)
            self._get_addon_settings()
            self._set_ui_controls()
            self._initialize_immich()
            self._validate_settings()
            if (self.setting_dbdates):
                # Asked to get unique date lists from the database, so try to get them
                try:
                    self.databaseAPI = DatabaseAPI(
                        self.setting_dbname,
                        self.setting_dbuser,
                        self.setting_dbpassword,
                        self.setting_dbhost,
                        self.setting_dbport,
                        ScreensaverAbortException,
                        lambda: self.Monitor.abortRequested()
                    )
                    self._get_db_dates()
                except Exception as e:
                    log(f"Database access failed: {e}")
                    log("Falling back to api access for dates")
                    self.setting_dbdates = False
                    self.databaseAPI.close()
            # Done with all of the initializations
            self._start_show()
        except ScreensaverAbortException:
            # ScreensaverAbortException thrown when the user presses a key
            return
        except Exception as e:
            # Notify for other problems that cause the screensavee to fail
            log(f"Exception type not handled: {str(e)}")
            notify(ADDON.getLocalizedString(EXCEPTION_TYPE_NOT_HANDLED),{str(e)})
        finally:
            # Close the Database on exit
            if (self.setting_dbdates):
                self.databaseAPI.close()
            # Close the api sessions on exit
            self.immichapi.close() 
             # Delete any temporary image files that have been retrieved
            self._delete_temporary_files(exiting=True)
            # Close everything
            xbmc.executebuiltin("Dialog.Close(all)")

    def _get_addon_settings(self):
        # Read addon settings
        self.setting_URL = ADDON.getSetting('URL')
        self.setting_APIKey = ADDON.getSetting('APIKey')
        self.setting_time = ADDON.getSettingInt('time')
        self.setting_limit = ADDON.getSettingInt('limit')
        self.setting_date = ADDON.getSettingBool('date')
        self.setting_tags = ADDON.getSettingBool('tags')
        self.setting_music = ADDON.getSettingBool('music')
        self.setting_clock = ADDON.getSettingBool('clock')
        self.setting_burst = ADDON.getSettingBool('burst')
        self.setting_panorama = ADDON.getSettingBool('panorama')
        self.setting_kenburns = ADDON.getSettingBool('kenburns')
        # convert float to hex value usable by the skin
        self.setting_dim = hex(int('%.0f' % (float(ADDON.getSettingInt('level')) * 2.55)))[2:] + 'ffffff'
        self.setting_dbdates = ADDON.getSettingBool('dbdates')
        self.setting_dbhost = ADDON.getSetting('dbhost')
        self.setting_dbport = ADDON.getSettingInt('dbport')
        self.setting_dbname = ADDON.getSetting('dbname')
        self.setting_dbuser = ADDON.getSetting('dbuser')
        self.setting_dbpassword = ADDON.getSetting('dbpassword')
        self.setting_favsOnly = ADDON.getSettingBool('favsOnly')
        self.setting_albums = ADDON.getSettingBool('albums')
        self.setting_albumname  = ADDON.getSettingBool('albumname')
        self.setting_usePreview = ADDON.getSettingBool('usePreview')
        self.empty_date_count = 0
        self.offset_adjustment = 0
        
    def _set_ui_controls(self):
        # Get the screensaver window id
        self.winid = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        # Get image and background controls from the xml
        self.image_controls = (self.getControl(1), self.getControl(2))
        self.background_controls = (self.getControl(3), self.getControl(4))
        # set the properties based on user settings
        self._set_prop('Dim', self.setting_dim)
        if self.setting_music:
            self._set_prop('Music', 'show')
        if self.setting_clock:
            self._set_prop('Clock', 'show')
        # Set the skin name so we can have different looks for different skins
        self._set_prop('SkinName',xbmc.getSkinDir())

    def _initialize_immich(self):
        self.immichapi = ImmichAPI(
            self.setting_APIKey,
            self.setting_URL,
            ScreensaverAbortException,
            lambda: self.Monitor.abortRequested()
        )

    def _validate_settings(self):
        # If use albums is specified, make sure some albums were selected
        if (self.setting_albums):
            self.albumlist = self.load_selected_albums()
            if self.albumlist:
                self.albumindices = list(range(len(self.albumlist)))
                random.shuffle(self.albumindices)
                self.albumindex = 0
            else:
                # No albums were found
                log("'Use Albums' is set but there are no albums selected. Setting value to False")
                self.setting_albums = False
        # If use favorites is specified, make sure some favorites exist
        if self.setting_favsOnly:
            args = {"size": 1, "isFavorite": True}
            response = self.immichapi.search_random(args)
            if len(response) == 0:
                # No favorites were found
                log("'Only Display Favorites' is set but there are no favorite images. Setting value to False")
                self.setting_favsOnly = False
    
    def load_selected_albums(self):
        if not ALBUMS_FILE.exists():
            return []
        try:
            data = json.loads(ALBUMS_FILE.read_text(encoding="utf-8"))
            return data.get("albums")
        except Exception:
            return []

    def _get_db_dates(self):
        if self.setting_albums:
            # get a list of all the distinct dates for each album
            self.db_album_dates = self._get_db_album_dates(self.albumlist)
        else:
            # get a list of all the distinct dates of the images
            self.distinct_dates = self._get_db_distinct_dates()
            # At the start of the show, use the first random date
            self.distinct_date_index = 0

    def _get_db_album_dates(self, albumlist):
        # for each album query for a list of unique dates in that album
        result = {}
        for album in albumlist:
            albumId = album["id"]
            query = f"""
                SELECT DISTINCT DATE(a."fileCreatedAt")
                FROM album_asset aa
                JOIN asset a ON a."id" = aa."assetId"
                WHERE aa."albumId" = '{albumId}';
            """
            rows = self.databaseAPI.exec_query(query)
            dates = [d for (d,) in rows]
            random.shuffle(dates)
            result[albumId] = {"date_index":0, "date_list": dates}
        return result

    def _get_db_distinct_dates(self):
        # Get a list of all the distinct dates of the images
        if self.setting_favsOnly:
            # Only get dates that contain favorites so we don't pick lots of days with no pictures to display
            query = ' SELECT DISTINCT DATE("fileCreatedAt") FROM asset WHERE "isFavorite" = TRUE; '
            distinct_dates = list(self.databaseAPI.exec_query(query))
            if len(distinct_dates) == 0:
                # There were NO dates found that had favorites, so don't limit pictures to favorites only
                self.setting_favsOnly = False
                log("'Only Display Favorites' is set but there are no favorite images. Setting value to False")
        if not self.setting_favsOnly:
            query = ' SELECT DISTINCT DATE("fileCreatedAt") FROM asset; '
            distinct_dates = list(self.databaseAPI.exec_query(query))
        # Randomize the order that the date groups will be shown
        random.shuffle(distinct_dates)
        return distinct_dates

    def _start_show(self):
        # start with first image control
        control_index = 0
        # loop until onScreensaverDeactivated is called
        while (not self.Monitor.abortRequested()):
            # Get a bunch of images from the same date
            image_groupings = self._get_image_groupings()
            for image_group in image_groupings:
                # an image_group is all pictures taken within 2 seconds of each other
                fastmode = True if (len(image_group) > 2 and self.setting_burst) else False
                for image in image_group:
                    # break if onScreensaverDeactivated is called
                    if self.Monitor.abortRequested():
                        raise ScreensaverAbortException

                    # download the image
                    image['local_path'] = self._get_local_filename_for_image(image)
                    if not self.immichapi.download_file(image['id'], image['local_path'], image['originalMimeType'], self.setting_usePreview):
                        #download failed, go to next image
                        continue

                    # logic to skip transitions when in fastmode
                    first_in_group = image is image_group[0]
                    last_in_group  = image is image_group[-1]
                    if not fastmode or (fastmode and (first_in_group or last_in_group)):
                        # Add background image to gui
                        self.background_controls[control_index].setImage(image['local_path'], False)
                        self._set_prop('Background', str(control_index))
                        # assign all of the requested and available info to the image
                        info = self._get_image_info(image)
                        image.update(info)
                        # Add image info to slide
                        self._set_info_fields(image, control_index)
                        self._set_prop('Info', str(control_index))

                    # Show the slide with animations
                    self.image_controls[control_index].setImage(image['local_path'], False)
                    timetowait, animation = self.get_animimation(image, fastmode, first_in_group, last_in_group)
                    self.image_controls[control_index].setAnimations(animation)
                    # About to show images, so turn off splash screen
                    self._set_prop('Splash', 'hide')

                    # display the image for the specified amount of time
                    if self.Monitor.waitForAbort(timetowait / 1000):
                        raise ScreensaverAbortException

                    # swap to next image control
                    control_index = 0 if control_index == 1 else 1

    def _get_image_groupings(self, update=False):    
        all_images_for_date = self._fetch_images_for_date()
        if len(all_images_for_date) == 0:
            # No displayable pictures found for this date
            self.empty_date_count +=1
            if self.empty_date_count > MAX_CONSECUTIVE_EMPTY_DATES:
                log(f"Made {MAX_CONSECUTIVE_EMPTY_DATES} date attempts with no images. Aborting")
                raise ScreensaverAbortException
            return []
        self.empty_date_count = 0
        image_groupings = self._group_images(all_images_for_date)
        # Return the requested number of pictures
        if self.setting_limit == 0 or (len(image_groupings) <= self.setting_limit):
            # Fewer picture for this date than max allowed, so display them all
            return image_groupings
        else:
            # More pictures on this date than the max allowed
            # Set a random offset into the list of pictures so we don't always start wtih the earliest picture on the date.
            offset = random.randrange(len(image_groupings) - self.setting_limit)
            if self.offset_adjustment != 0:
                offset = self.offset_adjustment
            return image_groupings[offset:offset+self.setting_limit]

    def _fetch_images_for_date(self):
        args = {}
        if self.setting_favsOnly:
            args["isFavorite"] = True
        if self.setting_albums:
            self.current_album = self.albumlist[self.albumindices[self.albumindex]]
            self.albumindex += 1
            if self.albumindex == len(self.albumindices):
                random.shuffle(self.albumindices)
                self.albumindex = 0
            args["albumIds"] = [self.current_album["id"]]
        date = self._get_random_date()
        args["takenAfter"] = f"{date}T00:00:00.000Z"
        args["takenBefore"] = f"{date}T23:59:59.999Z"
        args["withExif"] = "true"
        all_images_for_date = []
        for page in self.immichapi.search_metadata(args):
            for item in page:
                if item["originalMimeType"].lower().endswith(PICTURE_FORMATS):
                    exifinfo = item['exifInfo']
                    image = {
                        'localDateTime': item['localDateTime'],
                        'id': item['id'],
                        'originalFileName': item['originalFileName'],
                        'originalMimeType': item['originalMimeType'],
                        'Orientation': exifinfo['orientation']
                    }
                    if self.setting_tags:
                        image['Country'] = exifinfo['country']
                        image['State'] = exifinfo['state']
                        image['City'] = exifinfo['city']
                        image['Headline'] = exifinfo['description']
                    all_images_for_date.append(image)
        return all_images_for_date

    def _get_random_date(self):
        if (self.setting_dbdates):
            # Get some random date that at least one of the pictures was taken (each date is the single element of a list)
            if (self.setting_albums):
                # Find a date in the current album
                album_dates = self.db_album_dates[self.current_album["id"]]
                # Use the next date in the list of distinct dates for the selected album
                chosen_date = album_dates["date_list"][album_dates["date_index"]]
                # Next time choose a new date
                album_dates["date_index"] += 1
                if album_dates["date_index"] == len(album_dates["date_list"]):
                    # All of the dates have been used for the album, so start over with a shuffled list of all of the dates
                    album_dates["date_index"] = 0
                    random.shuffle(album_dates["date_list"])
            else:
                # Use the next date in the list of distinct dates
                chosen_date = self.distinct_dates[self.distinct_date_index][0]
                # Next time choose a new date
                self.distinct_date_index += 1
                if self.distinct_date_index == len(self.distinct_dates):
                    # All of the dates have been used, so start over with a shuffled list of all of the dates
                    random.shuffle(self.distinct_dates)
                    self.distinct_date_index = 0
        else:
            # Not using distinct dates from the database, so just get date from one random picture
            args={"size": 1}
            if self.setting_favsOnly:
                args.update({"isFavorite": True})
            if self.setting_albums:
                args.update({"albumIds":  [self.current_album["id"]]})
            response = self.immichapi.search_random(args)
            chosen_date = response[0]['localDateTime'][:10]
        # chosen_date = "2022-06-21"
        # chosen_date = "2017-08-03"; self.offset_adjustment = 15 # burst
        # chosen_date = "2001-06-02"
        # chosen_date = "2017-06-08"
        # chosen_date = "2013-08-01"; self.offset_adjustment = 71 # burst
        # chosen_date = "2021-05-07" # sublocation
        # chosen_date = "2021-04-11" # headline
        # chosen_date = "2010-10-03" # landscape and portrait mixed
        # chosen_date = "2025-12-17"; self.offset_adjustment = 43 # horizontal panorama
        # chosen_date = "2025-12-16"; self.offset_adjustment = 113 # vertical panorama
        # chosen_date = "2026-04-08"; self.offset_adjustment = 3 # cascais lighthouse
        # chosen_date = "2023-12-13" # heic
        # chosen_date = "2026-05-15" # heif
        # log(f"chosen date: {chosen_date}")
        return chosen_date

    def _group_images(self, all_images_for_date):
        # Sort by time, break ties with filename - pictures taken same second are ordered correctly
        all_images_for_date.sort(key=lambda x: (x["localDateTime"], x["originalFileName"]))
        group_index = 0
        # Put the first picture in the first group
        image_groupings=[[all_images_for_date[0]]]
        # Get date and time with milliseconds, but without time zone
        prev_image_date_object = datetime.fromisoformat(all_images_for_date[0]['localDateTime'].rstrip("Z"))
        # Go through the rest of the images
        image_index = 1
        while image_index < len(all_images_for_date):
            # Get date and time with milliseconds, but without time zone
            this_image_date_object = datetime.fromisoformat(all_images_for_date[image_index]['localDateTime'].rstrip("Z"))
            # Calculate difference between when this picture was taken and when the last picture was taken
            datediff = this_image_date_object - prev_image_date_object
            if datediff.total_seconds() <= 2:
                # image within two seconds of previous image go in same group
                image_groupings[group_index].append(all_images_for_date[image_index])
                if not self.setting_burst:
                    # Only store the first and last images if not showing them in burst mode
                    if len(image_groupings[group_index]) > 2:
                        image_groupings[group_index].pop(1)
            else:
                group_index += 1
                image_groupings.append([all_images_for_date[image_index]])
            prev_image_date_object = this_image_date_object
            image_index+=1
        return image_groupings
    
    def _get_local_filename_for_image(self, image):
        # We store the downloaded images in the addon's userdata folder
        return str(ADDON_USERDATA_FOLDER / (image['id'] + IMMICH_TEMP_FILE_EXTENSION))

    def _get_image_info(self, image):
        info = {}
        iptc_info = {}
        # Get extra info for this image
        if self.setting_date:
            imgdatetime = image['localDateTime'][:18]
            info['Date'] = time.strftime('%A %B %e, %Y',time.strptime(imgdatetime, '%Y-%m-%dT%H:%M:%S'))
            info['Time'] = time.strftime('%I:%M %p',time.strptime(imgdatetime, '%Y-%m-%dT%H:%M:%S'))
        if self.setting_albums and self.setting_albumname:
            info['AlbumName'] = self.current_album['albumName']
        if self.setting_tags:
            # Get more info from the actual file.
            iptc_info = self._get_iptcinfo(self._get_local_filename_for_image(image))
        image_info = {**info, **iptc_info}
        return image_info

    def _get_iptcinfo(self, filename):
        fields = {
            "Headline": "headline",
            "Caption": "caption/abstract",
            "Sublocation": "sub-location",
            "City": "city",
            "State": "province/state",
            "Country": "country/primary location name",
        }
        iptcinfo = {}
        try:
            iptc = IPTCInfo(filename)
            for key, tag in fields.items():
                if not iptc[tag]:
                    continue
                raw = bytes(iptc[tag])
                try:
                    iptcinfo[key] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    iptcinfo[key] = raw.decode("latin-1", errors="replace")
            return iptcinfo
        except Exception:
            return iptcinfo

    def _set_info_fields(self, image, order):
        # Assign whatever info was found into the correct labels
        for prop in ('AlbumName', 'Headline', 'Caption', 'Sublocation', 'City', 'State', 'Country', 'Date', 'Time'):
            if prop in image:
                self._set_prop(prop+str(order),image[prop])
            else: 
                self._clear_prop(prop+str(order))

    def get_animimation(self, image, fastmode, first_in_group, last_in_group):
        if fastmode and not (first_in_group or last_in_group):
            return 30, []
        FADE_FRACTION = 0.2
        EXTRA_TIME_FRACTION = 0.25
        slideshow_ms = self.setting_time * 1000
        fade_ms = min(slideshow_ms * FADE_FRACTION,2000)
        if fastmode:
            FADEIN_EFFECT =  ['conditional', f'effect=fade start=0 end=100 time={fade_ms} reversible=false condition=true']
            FADEOUT_EFFECT = ['conditional', f'effect=fade start=100 end=0 time={fade_ms*2} delay={slideshow_ms+(2*fade_ms)} reversible=false condition=true']
            if first_in_group:
                return slideshow_ms / 2,[FADEIN_EFFECT]
            else:
                return slideshow_ms,[FADEOUT_EFFECT]

        screen_w = self.winid.getWidth()
        screen_h = self.winid.getHeight()
        img_w, img_h = imagesize.get(image['local_path'])
        aspect_ratio = max(img_w, img_h) / min(img_w, img_h)
        PANORAMA_RATIO = 1.85
        if (self.setting_panorama and aspect_ratio >= PANORAMA_RATIO):
            orientation = image['Orientation']
            if img_w > img_h and orientation not in ("8", "6"):            # horizontal panorama
                baseline_h = screen_w * (img_h / img_w)                    #   scale factor to make image height fit the screen
                scale_start = scale_end = (screen_h / baseline_h) * 100.0  
                scaled_w = screen_w * (scale_start / 100.0)                #   width of scaled image
                slide_x = ((scaled_w / 2.0) - (screen_w / 2.0))            #   amount to shift to bring left side on screen
                slide_y = 0                                                #   don't shift in y direction
                total_ms = int(slideshow_ms * (scaled_w / screen_w))       #   increase the time so rate is the same
                duration_ms = total_ms - ((slideshow_ms * EXTRA_TIME_FRACTION) * (scaled_w / screen_w))      #   fudge factor to make fading work
            else:                                                          # verticalal panorama
                baseline_w = screen_h * (img_h / img_w)                    #   scale factor to make image width fit the screen
                scale_start = scale_end = (screen_w / baseline_w) * 100.0
                scaled_h = screen_h * (scale_start / 100.0)                #   height of scaled image
                slide_y = -((scaled_h / 2.0) - (screen_h / 2.0))           #   amount to shift to bring bottom on screen
                slide_x = 0                                                #   dont shift in the x direction
                total_ms = int(slideshow_ms * (scaled_h / screen_h))       #   increase the time so rate is the same
                duration_ms = total_ms - ((slideshow_ms * EXTRA_TIME_FRACTION) * (scaled_h / screen_h))      #   fudge factor to make fading work
        else: # Not a panorama slide
            if self.setting_kenburns:
                base_scale = 115 + self.setting_time
                scale_h = screen_h * (base_scale / 100.0)
                scale_w = screen_w * (base_scale / 100.0)
                slide_x = random.randint(-1,1) * ((scale_w - screen_w) / 2.0)
                slide_y = random.randint(-1,1) * ((scale_h - screen_h) / 2.0)
                scale_start = base_scale if (slide_x,slide_y) != (0,0) else 100 
                scale_end = base_scale * 1.2 if (slide_x,slide_y) != (0,0) else base_scale * 1.3
            else: # Just crossfade
                slide_x = slide_y = 0
                scale_start = scale_end = 100
            duration_ms = slideshow_ms
            total_ms = slideshow_ms + (slideshow_ms * EXTRA_TIME_FRACTION)

        zoom_ms = slide_ms = fadeout_start = total_ms + (slideshow_ms * FADE_FRACTION)
        animation = [
                        ["conditional", f"effect=fade  time={fade_ms}  start=0 end=100                                     condition=true"],
                        ["conditional", f"effect=slide time={slide_ms} start={slide_x},{slide_y} end={-slide_x},{-slide_y} condition=true"],
                        ["conditional", f"effect=zoom  time={zoom_ms}  start={scale_start} end={scale_end} center=auto     condition=true"],
                        ["conditional", f"effect=fade  time={fade_ms}  start=100 end=0 delay={fadeout_start}               condition=true"],
                    ]
        return duration_ms, animation

    # Utility functions
    def _delete_temporary_files(self, exiting=False):
        try:
            for file in ADDON_USERDATA_FOLDER.glob(f"*{IMMICH_TEMP_FILE_EXTENSION}"):
                if exiting or (file.stat().st_mtime < (time.time() - (self.setting_time * 30))):
                    file.unlink(missing_ok=True)
        except:
            pass

    def _set_prop(self, name, value):
        self.winid.setProperty('Screensaver.%s' % name, value)

    def _clear_prop(self, name):
        self.winid.clearProperty('Screensaver.%s' % name)

    def _exit(self):
        # exit when onScreensaverDeactivated gets called
        self.close()

class ScreensaverAbortException(Exception):
    # Used to end the screensaver when a key is pressed
    pass

# Notify when screensaver is to stop
class MyMonitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        self.action = kwargs['action']

    def onScreensaverDeactivated(self):
        self.action()

    def onDPMSActivated(self):
        self.action()
