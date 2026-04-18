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
#     8. There is the option to randomly choose from a list of unique picture dates,
#        rather than choosing a random picture to get a date for the image group.
#        This allows each date to be chosen with the same probability, rather than
#        dates with more pictures being chosen more frequently. Requires you to set
#        up direct access to the immich database.

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import os
import glob
import sys
import random
import time
from datetime import datetime
import json
import requests
from iptcinfo3 import IPTCInfo
# Turn off all the warnings from IPTCInfo
import logging
logging.getLogger("iptcinfo").setLevel(logging.ERROR)

sys.path.insert(0, os.path.join(sys.path[0], 'modules'))
import pg8000.dbapi # For postgressql database access
import imagesize

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_USERDATA_FOLDER = xbmcvfs.translatePath("special://profile/addon_data/"+ADDON_ID)+'/'

def log(msg, level=xbmc.LOGINFO):
        filename = os.path.basename(sys._getframe(1).f_code.co_filename)
        lineno  = str(sys._getframe(1).f_lineno)
        xbmc.log(str("[%s] line %5d in %s >> %s"%(ADDON.getAddonInfo('name'), int(lineno), filename, msg.__str__())), level)

# Formats that can be displayed in a slideshow
PICTURE_FORMATS = ('bmp', 'jpeg', 'jpg', 'gif', 'png', 'tiff', 'mng', 'ico', 'pcx', 'tga')

IMMICH_TEMP_FILE_EXTENSION = '.immich-tmp'

class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        pass

    def onInit(self):
        try:
            # Init the monitor class to catch onscreensaverdeactivated calls
            self.Monitor = MyMonitor(action = self._exit)
            # Get addon settings
            self._get_settings()
            if (self.slideshow_dbdates):
                self.IMMICHDB = pg8000.dbapi.Connection(
                    database=self.slideshow_dbname,
                    user=self.slideshow_dbuser,
                    password=self.slideshow_dbpassword,
                    host=self.slideshow_dbhost,
                    port=self.slideshow_dbport
                )
                #get a list of all the distinct dates of the images
                self.distinct_dates = self._get_distinct_dates()
                # At the start of the show, use the first random date
                self.distinct_date_index = 0

             # Set UI Component information
            self._set_ui_controls()
            # Start the show
            self.stop = False
            self._start_show()
        # Catch communication exceptions
        except SlideshowException as se:
            text = '[B]'+se.header+'[/B]'+'\n'+se.message+'\n'
            for key, value in se.network_response.items():
                text = text+key+': '+str(value)+'\n'
            xbmc.executebuiltin("Dialog.Close(all)")
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_ID, text)
        finally:
            # Delete any temporary image files that have been retrieved
            self._delete_temporary_files(exiting=True)

    def _get_distinct_dates(self):
        # Get a list of all the distinct dates of the images
        query = ' SELECT DISTINCT DATE("fileCreatedAt") FROM asset; '
        distinct_dates = list(self._exec_query(query))
        # Randomize the order that the date groups will be shown
        random.shuffle(distinct_dates)
        return distinct_dates

    def _get_settings(self):
        # Read addon settings
        self.slideshow_URL = ADDON.getSetting('URL')
        self.slideshow_APIKey = ADDON.getSetting('APIKey')
        self.slideshow_useAlbum = ADDON.getSettingBool('useAlbum')
        # Convert to array of strings
        uuid_str = ADDON.getSetting('albumUUID')
        self.slideshow_AlbumUUID = [s.strip() for s in uuid_str.split(',')] if uuid_str.strip() else None
        self.slideshow_time = ADDON.getSettingInt('time')
        self.slideshow_limit = ADDON.getSettingInt('limit')
        self.slideshow_date = ADDON.getSettingBool('date')
        self.slideshow_tags = ADDON.getSettingBool('tags')
        self.slideshow_music = ADDON.getSettingBool('music')
        self.slideshow_clock = ADDON.getSettingBool('clock')
        self.slideshow_burst = ADDON.getSettingBool('burst')
        self.slideshow_panorama = ADDON.getSettingBool('panorama')
        self.slideshow_kenburns = ADDON.getSettingBool('kenburns')
        # convert float to hex value usable by the skin
        self.slideshow_dim = hex(int('%.0f' % (float(ADDON.getSettingInt('level')) * 2.55)))[2:] + 'ffffff'
        self.slideshow_dbdates = ADDON.getSettingBool('dbdates')
        self.slideshow_dbhost = ADDON.getSetting('dbhost')
        self.slideshow_dbport = ADDON.getSettingInt('dbport')
        self.slideshow_dbname = ADDON.getSetting('dbname')
        self.slideshow_dbuser = ADDON.getSetting('dbuser')
        self.slideshow_dbpassword = ADDON.getSetting('dbpassword')
        self.slideshow_offset_adjustment = 0

    def _set_ui_controls(self):
        # Get the screensaver window id
        self.winid = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        # Get image controls from the xml
        self.image_control1 = self.getControl(1)
        self.image_control2 = self.getControl(2)
        self.background_image1 = self.getControl(3)
        self.background_image2 = self.getControl(4)
        # set the dim property
        self._set_prop('Dim', self.slideshow_dim)
        # show music info during slideshow if enabled
        if self.slideshow_music:
            self._set_prop('Music', 'show')
        # show clock if enabled
        if self.slideshow_clock:
            self._set_prop('Clock', 'show')
        # Set the skin name so we can have different looks for different skins
        self._set_prop('SkinName',xbmc.getSkinDir())

    def _start_show(self):
        # start with image 1
        current_image_control = self.image_control1
        order = [1,2]
        # loop until onScreensaverDeactivated is called
        while (not self.Monitor.abortRequested()) and (not self.stop):
            # Get the next grouping of pictures
            image_groupings = self._get_image_groupings()
            for image_group in image_groupings:
                # Delete any temporary image files that have been retrieved
                self._delete_temporary_files()
                # fastmode is true when we find pictures taken in burst mode
                fastmode = True if (len(image_group) > 2 and self.slideshow_burst) else False
                # iterate through all the images in the group
                for image in image_group:
                    image_uuid = image[1]
                    local_img_name = ADDON_USERDATA_FOLDER+image_uuid+IMMICH_TEMP_FILE_EXTENSION
                    if not self._download_file(f'{self.slideshow_URL}/api/assets/{image_uuid}/original', local_img_name):
                        # Download failed, go to next image
                        continue

                    first_in_group = image == image_group[0]
                    last_in_group = image == image_group[-1]
                    if not fastmode or (fastmode and (first_in_group or last_in_group)):
                        # Add background image to gui
                        if order[0] == 1:
                            self.background_image1.setImage(local_img_name, False)
                        else:
                            self.background_image2.setImage(local_img_name, False)
                        # add fade anim to background images
                        self._set_prop('Fade%d' % order[0], '0')
                        self._set_prop('Fade%d' % order[1], '1')
                        # Add picture information to slide
                        # Only show label transition animation when changing to a new date
                        self._set_info_fields(image,transition=(image_group == image_groupings[0])) 

                    # Show the slide
                    current_image_control.setImage(local_img_name, False)
                    animation,timetowait = self.get_animimation(local_img_name, fastmode, first_in_group, last_in_group)
                    current_image_control.setAnimations(animation)

                    if fastmode:
                        timetowait = 0

                    # have shown images, so turn off splash screen
                    self._set_prop('Splash', 'hide')

                    # display the image for the specified amount of time
                    count = timetowait
                    while (not self.Monitor.abortRequested()) and (not self.stop) and count > 0:
                        count -= 1000
                        xbmc.sleep(1000)

                    # define next image
                    if current_image_control == self.image_control1:
                        current_image_control = self.image_control2
                        order = [2,1]
                    else:
                        current_image_control = self.image_control1
                        order = [1,2]

                    # break out of the 'images in image_group loop' if onScreensaverDeactivated is called
                    if  self.stop or self.Monitor.abortRequested():
                        self.stop = True
                        break

                # break out of the 'image_group in image_groupings' loop if onScreensaverDeactivated is called
                if  self.stop or self.Monitor.abortRequested():
                    self.stop = True
                    break

    def _get_image_groupings(self, update=False):
        if (self.slideshow_useAlbum):
            payload = json.dumps({"size": 1000, "albumIds":self.slideshow_AlbumUUID})            
        else:
            # Ask for a random date
            chosen_date = self._get_random_date()

            # Get all of the pictures taken on the chosen date.
            takenAfter = chosen_date+'T00:00:00.000Z'
            takenBefore = chosen_date+'T23:59:59.999Z'
            payload = json.dumps({"takenAfter": takenAfter, "takenBefore": takenBefore, "size": 1000})
        all_images_for_date=[]
        more = True
        while more:
            response = self._api_call("POST", "/api/search/metadata", payload)
            # Store (Datetime, id, filename, path to file)
            for item in response['assets']['items']:
                # Make sure only displayable pictures are used - check mimetype of each item
                if item["originalMimeType"].lower().endswith(PICTURE_FORMATS):
                    all_images_for_date.append((item['localDateTime'],item["id"],item['originalFileName'],item['originalPath']))
            if response['assets']['nextPage']:
                if (self.slideshow_useAlbum):
                    payload = json.dumps({"size": 1000, "albumIds":self.slideshow_AlbumUUID, "page": response['assets']['nextPage']})
                else:
                    payload = json.dumps({"takenAfter": takenAfter, "takenBefore": takenBefore, "size": 1000, "page": response['assets']['nextPage']})
            else:
                more = False

        if len(all_images_for_date) == 0:
            # No displayable pictures found for this date
            return []

        #Sort by time, break ties with filename - pictures taken same second are ordered correctly
        all_images_for_date.sort(key=lambda x: (x[0],x[2]))

        # Group together pictures taken in burst mode
        group_index = 0
        # Put the first picture in the first group
        image_groupings=[[all_images_for_date[0]]]
        # Get date and time with milliseconds, but without time zone
        image_datetime = all_images_for_date[0][0][:23]
        prev_image_date_object = datetime.fromtimestamp(time.mktime(time.strptime(image_datetime, '%Y-%m-%dT%H:%M:%S.%f')))
        # Go through the rest of the images
        image_index = 1
        while image_index < len(all_images_for_date):
            # Get date and time with milliseconds, but without time zone
            image_datetime = all_images_for_date[image_index][0][:23]
            this_image_date_object = datetime.fromtimestamp(time.mktime(time.strptime(image_datetime, '%Y-%m-%dT%H:%M:%S.%f')))
            # Calculate difference between when this picture was taken and when the last picture was taken
            datediff = this_image_date_object - prev_image_date_object
            if datediff.total_seconds() <= 2:
                # image within two seconds of previous image go in same group
                image_groupings[group_index].append(all_images_for_date[image_index])
                if not self.slideshow_burst:
                    # Only store the first and last images if not showing them in burst mode
                    if len(image_groupings[group_index]) > 2:
                        image_groupings[group_index].pop(1)
            else:
                group_index += 1
                image_groupings.append([all_images_for_date[image_index]])
            prev_image_date_object = this_image_date_object
            image_index+=1

        # Return the requested number of pictures
        if self.slideshow_limit == 0 or (len(image_groupings) <= self.slideshow_limit):
            # Fewer picture for this date than max allowed, so display them all
            return image_groupings
        else:
            # More pictures on this date than the max allowed
            # Set a random offset into the list of pictures so we don't always start wtih the earliest picture on the date.
            offset = random.randrange(len(image_groupings) - self.slideshow_limit)
            if self.slideshow_offset_adjustment != 0:
                offset = self.slideshow_offset_adjustment
            return image_groupings[offset:offset+self.slideshow_limit]

    def _get_random_date(self):
        if (self.slideshow_dbdates):
            # Use the next date in the list of distinct dates, then get all of the pictures taken on the same date.
            # Set a random offset into the list of pictures so we don't always start wtih the earliest picture on the date.

            # Get some random date that at least one of the pictures was taken (each date is the single element of a list)
            chosen_date = self.distinct_dates[self.distinct_date_index][0]
            # Next time choose a new date
            self.distinct_date_index += 1
            if self.distinct_date_index == len(self.distinct_dates):
                # All of the dates have been used, so start over with a new list of all of the dates
                random.shuffle(self.distinct_dates)
                self.distinct_date_index = 0
        else:
            # Just get one random picture
            response = self._api_call("POST", "/api/search/random", json.dumps({"size": 1}))
            # Get the date that the picture was taken
            chosen_date = response[0]['localDateTime'][:10]

        # chosen_date = "2022-06-21"
        # chosen_date = "2017-08-03"; self.slideshow_offset_adjustment = 15 # burst
        # chosen_date = "2001-06-02"
        # chosen_date = "2017-06-08"
        # chosen_date = "2013-08-01"; self.slideshow_offset_adjustment = 71 # burst
        # chosen_date = "2021-05-07" # sublocation
        # chosen_date = "2021-04-11" # headline
        # chosen_date = "2010-10-03" # landscape and portrait mixed
        # chosen_date = "2025-12-17"; self.slideshow_offset_adjustment = 43 # horizontal panorama
        # chosen_date = "2025-12-16"; self.slideshow_offset_adjustment = 113 # vertical panorama
        return chosen_date

    def _get_local_filename_for_image(self, image):
        # We store the downloaded images in the addon's userdata folder
        return ADDON_USERDATA_FOLDER+image[1]+IMMICH_TEMP_FILE_EXTENSION

    def _set_info_fields(self, image, transition=True):
        # Get info about the image
        info = self._get_image_info(image)

        # Transition between two sets of info if requested
        if transition:
            self._set_prop('FadeoutLabels' ,'1')
            xbmc.sleep(750)
        # Assign whatever info was found into the correct labels
        if 'Headline' in info:
            self._set_prop('Headline',info['Headline'])
        else:
            self._clear_prop('Headline')
        if 'Caption' in info:
            self._set_prop('Caption',info['Caption'])
        else:
            self._clear_prop('Caption')
        if 'Sublocation' in info:
            self._set_prop('Sublocation',info['Sublocation'])
        else:
            self._clear_prop('Sublocation')
        if 'City' in info:
            self._set_prop('City',info['City'])
        else:
            self._clear_prop('City')
        if 'State' in info:
            self._set_prop('State',info['State'])
        else:
            self._clear_prop('State')
        if 'Country' in info:
            self._set_prop('Country',info['Country'])
        else:
            self._clear_prop('Country')
        if 'Date' in info:
            self._set_prop('Date',info['Date'])
        else:
            self._clear_prop('Date')
        if 'Time' in info:
            self._set_prop('Time',info['Time'])
        else:
            self._clear_prop('Time')

        # Complete the transition to the new set of info
        if transition:
            self._set_prop('FadeinLabels', '1')
            xbmc.sleep(750)
        self._set_prop('FadeoutLabels', '0')

    def _get_image_info(self, image):
        immich_info = {}
        iptc_info = {}
        # Get info about image from the immich API
        response = self._api_call("GET", "/api/assets/"+image[1], json.dumps({}))
        exifinfo = response['exifInfo']
        self._set_prop('orientation',exifinfo['orientation'])
        # Get all of the info for this image
        if self.slideshow_date:
            # Get the date and time the image was taken
            imgdatetime = image[0][:18]
            immich_info['Date'] = time.strftime('%A %B %e, %Y',time.strptime(imgdatetime, '%Y-%m-%dT%H:%M:%S'))
            immich_info['Time'] = time.strftime('%I:%M %p',time.strptime(imgdatetime, '%Y-%m-%dT%H:%M:%S'))
        if self.slideshow_tags:
            immich_info['Country'] = exifinfo['country']
            immich_info['State'] = exifinfo['state']
            immich_info['City'] = exifinfo['city']
            immich_info['Headline'] = exifinfo['description']
            # Get more info from the actual file.
            iptc_info = self._get_iptcinfo(self._get_local_filename_for_image(image))
        # Info in file (iptc_info) overrides info from immich (immich_info)
        image_info = {**immich_info, **iptc_info}
        return image_info

    def _get_iptcinfo(self, filename):
        # Retrieve info directly from the file
        iptc_info = {}
        try:
            iptc = IPTCInfo(filename)
            if iptc['headline']:
                iptc_info['Headline'] = iptc['headline']
            if iptc['caption/abstract']:
                iptc_info['Caption'] = iptc['caption/abstract']
            if iptc['sub-location']:
                iptc_info['Sublocation'] = iptc['sub-location']
            if iptc['city']:
                iptc_info['City'] = iptc['city']
            if iptc['province/state']:
                iptc_info['State'] = iptc['province/state']
            if iptc['country/primary location name']:
                iptc_info['Country'] = iptc['country/primary location name']
        except:
            pass
        return iptc_info

    def get_animimation(self, img_path, fastmode, first_in_group, last_in_group):
        if fastmode and not (first_in_group or last_in_group):
            return [], 0

        show_ms = int(self.slideshow_time * 1000)
        fade_ms = min(2000, show_ms*0.2)
        adjust_ms = fade_ms * 2 if last_in_group else fade_ms

        FADEIN_EFFECT = ['conditional', f'effect=fade start=0 end=100 time={fade_ms} condition=true']
        FADEOUT_EFFECT = ['conditional', f'effect=fade start=100 end=0 time={fade_ms} delay={show_ms+fade_ms+adjust_ms} condition=true']
        
        if fastmode:
            if first_in_group:
                return [FADEIN_EFFECT],max(fade_ms,int(show_ms / 4.0))
            else:
                return [FADEOUT_EFFECT],max(fade_ms,int(show_ms / 4.0))

        screen_w = self.winid.getWidth()
        screen_h = self.winid.getHeight()
        center_x =  (screen_w / 2.0)
        center_y =  (screen_h / 2.0)
        if (self.slideshow_panorama):
            # Image and screen dimensions
            img_w, img_h = imagesize.get(img_path)
            PANORAMA_RATIO = 1.85
            aspect_ratio = max(img_w, img_h) / min(img_w, img_h)
            if aspect_ratio >= PANORAMA_RATIO:
                orientation = self.winid.getProperty('Screensaver.orientation')
                if img_w > img_h and orientation not in ("8", "6"): # horizontal panorama
                    # Find scale factor to make image height fit the screen
                    baseline_h = screen_w * (img_h / img_w)
                    scale = (screen_h / baseline_h)
                    # Get width of zoomed image so we know how much to pan
                    zoomed_w = screen_w * scale
                    # Figure out how much of the image is off of the screen when centered
                    slide_x = (screen_w * (screen_w - zoomed_w)) / zoomed_w
                    slide_y = 0
                    zoom_y = center_y
                    zoom_x = 0
                    # Increase the time for the slide so animation not too fast
                    total_ms = show_ms * (zoomed_w / screen_w)
                    adjust_ms = (total_ms - show_ms)*(screen_w/zoomed_w)
                else: # vertical panorama
                    # Find scale factor to make image width fit the screen
                    baseline_w = screen_h * (img_h / img_w) 
                    scale = (screen_w / baseline_w)
                    # Get height of zoomed image so we know how much to pan
                    zoomed_h = screen_h * scale
                    # Figure out how much of the image is off of the screen when centered
                    slide_y = (screen_h * (zoomed_h - screen_h)) / zoomed_h
                    slide_x = 0
                    zoom_y = screen_h
                    zoom_x = center_x
                    # Increase the time for the slide so animation not too fast
                    total_ms = show_ms * (zoomed_h / screen_h)
                    adjust_ms = (total_ms - show_ms)*(screen_h/zoomed_h)
                # Zoom so that image fits the screen
                zoom = scale * 100
                zoom_ms = total_ms
                slide_start = fade_ms
                slide_ms  = total_ms + adjust_ms
                fadeout_start = slide_ms
                duration = total_ms - adjust_ms
                animation = [
                    FADEIN_EFFECT,
                    ["conditional", f"condition=true effect=zoom  time={zoom_ms}  start={zoom} end={zoom}              center={zoom_x},{zoom_y}"],
                    ["conditional", f"condition=true effect=slide time={slide_ms} start=0,0    end={slide_x},{slide_y} delay={slide_start}"],
                    ["conditional", f"condition=true effect=fade  time={fade_ms}  start=100    end=0                   delay={fadeout_start}"]
                ]
                return animation,duration
        if self.slideshow_kenburns:
            zoom = 130 + self.slideshow_time
            zoom_x = center_x + (center_x * random.randint(-1,1))
            zoom_y = center_y + (center_y * random.randint(-1,1))
            zoom_ms = show_ms + fade_ms + fade_ms + adjust_ms
            animation = [
                FADEIN_EFFECT,
                ["conditional", f"condition=true effect=zoom  time={zoom_ms}  start=100 end={zoom} center={zoom_x},{zoom_y}"],
                FADEOUT_EFFECT
            ]
            return animation,show_ms
        return [FADEIN_EFFECT,FADEOUT_EFFECT],show_ms

    # Utility functions
    def _exec_query(self,query):
        cursor = self.IMMICHDB.cursor()
        cursor.execute(query)
        records = []
        while True:
            rows = cursor.fetchmany(100)
            if not rows:
                break
            records.extend(rows)
        return records

    def _download_file(self, url, local_filename):
        try:
            with requests.get(url, stream=True, headers={'x-api-key': self.slideshow_APIKey}) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            attempts = 0
            while not os.path.exists(local_filename):
                xbmc.sleep(100)
                attempts += 1
                if attempts > 100:
                    return False
            return True
        except:
            return False

    def _delete_temporary_files(self, exiting=False):
        try:
            for filename in glob.glob(ADDON_USERDATA_FOLDER+'*'+IMMICH_TEMP_FILE_EXTENSION):
                if exiting or (os.path.getmtime(filename) < (time.time() - (self.slideshow_time*30))):
                    os.remove(filename)
        except:
            pass

    def _api_call(self, action, api, payload):
        response = {}
        try:
            headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-api-key': self.slideshow_APIKey
            }
            resp = requests.request(action, self.slideshow_URL+api, headers=headers, data=payload)
            response = json.loads(resp.text)
            if resp.status_code == 401:
                self.stop = True;
                raise SlideshowException(ADDON.getLocalizedString(30420),ADDON.getLocalizedString(30430),response)
            elif resp.status_code != 200:
                self.stop = True;
                raise SlideshowException(ADDON.getLocalizedString(30400),ADDON.getLocalizedString(30410),response)
        except SlideshowException:
            raise
        except requests.exceptions.ConnectionError as ce:
            raise SlideshowException(ADDON.getLocalizedString(30400), str(ce))
        return response

    def _set_prop(self, name, value):
        self.winid.setProperty('Screensaver.%s' % name, value)

    def _clear_prop(self, name):
        self.winid.clearProperty('Screensaver.%s' % name)

    def _exit(self):
        # exit when onScreensaverDeactivated gets called
        self.stop = True
        # clear our properties on exit
        self._clear_prop('Fade1')
        self._clear_prop('Fade2')
        self._clear_prop('FadeinLabels')
        self._clear_prop('FadeoutLabels')
        self._clear_prop('Dim')
        self._clear_prop('Music')
        self._clear_prop('Clock')
        self._clear_prop('Splash')
        self._clear_prop('SkinName')
        self._clear_prop('Headline')
        self._clear_prop('Caption')
        self._clear_prop('Sublocation')
        self._clear_prop('City')
        self._clear_prop('State')
        self._clear_prop('Country')
        self._clear_prop('Date')
        self._clear_prop('Time')
        self.close()

class SlideshowException(Exception):
    def __init__(self,header,message,network_response={}):
        self.header = header
        self.message = message
        self.network_response = network_response

# Notify when screensaver is to stop
class MyMonitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        self.action = kwargs['action']

    def onScreensaverDeactivated(self):
        self.action()

    def onDPMSActivated(self):
        self.action()
