import requests
import json
import time
import xbmc
import xbmcaddon
import sys
import os
sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'lib'))
from services import log, notify

ADDON = xbmcaddon.Addon()

CONNECTION_ERROR = 30900
CONNECTION_TIMEOUT = 30910
AUTHORIZATION_ERROR = 30920
AUTHORIZATION_ERROR_MESSAGE = 30921
API_FAILURE = 30930
STATUS_CODE = 30931

class ImmichAPI:
    def __init__(self, apikey, url, abort_exception, abort_function):
        self.apikey = apikey
        self.url = url.rstrip("/")
        self.abort_exception = abort_exception
        self.abort_function = abort_function
        self.api_session = requests.Session()
        self.api_session.headers.update({
            "x-api-key": self.apikey,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.download_file_session = requests.Session()
        self.download_file_session.headers.update({
            "x-api-key": self.apikey,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive"
        })
        requests.packages.urllib3.disable_warnings()

    def search_random(self,args):
        resp = self._api_call("POST", "/api/search/random", payload=args)
        return json.loads(resp.text)

    def get_asset(self, assetUUID):
        resp =self._api_call("GET", "/api/assets/"+assetUUID)
        return json.loads(resp.text)

    def get_albums(self):
        try: 
            resp = self._api_call("GET", "/api/albums")
            return json.loads(resp.text)
        except:
            return None

    def search_metadata(self, args):
        payload = dict(args)
        payload["size"] = 1000
        while True:
            resp = self._api_call("POST", "/api/search/metadata", payload=payload)
            data = resp.json()
            yield data["assets"]["items"]
            next_page = data["assets"]["nextPage"]
            if not next_page:
                break
            payload["page"] = next_page

    def _api_call(self,method, endpoint, payload=None):
        notify_header = ""
        notify_message = ""
        log_message = ""
        timeout=(0.5, 1.0)
        delays = [0.5, 1, 2]  # retry backoff
        for attempt, delay in enumerate(delays, start=1):
            # Allow Screensaver to abort mid‑retry
            if self.abort_function():
                # User requested end of show
                raise self.abort_exception()
            try:
                resp = self.api_session.request(method, self.url + endpoint, json=payload, timeout=timeout)
                if resp.status_code == 401:
                    # Handle Auth error
                    notify_header = ADDON.getLocalizedString(AUTHORIZATION_ERROR)
                    notify_message = ADDON.getLocalizedString(AUTHORIZATION_ERROR_MESSAGE)
                    log_message = f"Authorization Error: API Key may be invalid. {resp.text}"
                    break
                elif resp.status_code != 200:
                    # Handle other http errors
                    notify_header = ADDON.getLocalizedString(API_FAILURE)
                    notify_message = f"{ADDON.getLocalizedString(STATUS_CODE)}: {resp.status_code}"
                    log_message = f"API Failure - Status Code: {resp.status_code}. {resp.text}"
                    break
                else:
                    # API call succeeded
                    return resp
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as excp:
                if attempt == len(delays):
                    # Handle network exception after max retries
                    if isinstance(excp, requests.exceptions.ConnectionError):
                        notify_header = ADDON.getLocalizedString(CONNECTION_ERROR)
                        log_message = "Connection Error -"
                    else:
                        notify_header = ADDON.getLocalizedString(CONNECTION_TIMEOUT)
                        log_message = "Connection Timeout -"
                    notify_message = str(excp).split("Caused by")[-1].strip()
                    log_message = log_message + notify_message
                # Wait before retrying
                end = time.time() + delay
                while time.time() < end:
                    if self.abort_function():
                        # User requested end of show
                        raise self.abort_exception()
                    time.sleep(0.1)
            except Exception as e:
                # Handle other exceptions
                notify_header = ADDON.getLocalizedString(API_FAILURE)
                notify_message = str(type(e).__name__)
                log_message = f"API Failure - {str(type(e).__name__)}"
                break
        log(log_message,level=xbmc.LOGERROR)
        notify(notify_header,notify_message)
        raise self.abort_exception()

    def download_file(self, fileUUID, local_filename, mime_type=None, use_preview=False):
        if use_preview or mime_type.lower().endswith(("heic", "heif")):
            # If HEIC/HEIF, get thumbnail - kodi doesn't support these
            url = f"{self.url}/api/assets/{fileUUID}/thumbnail?size=preview"
        else:
            # All other formats: request true original, full resolution
            url = f"{self.url}/api/assets/{fileUUID}/original"
        try:
            resp = self.download_file_session.get(url, stream=True, timeout=(1.0, 10.0))
            if resp.status_code != 200:
                return False
            with open(local_filename, "wb", buffering=0) as f:
                for chunk in resp.raw.stream(4* 1024 * 1024):
                    if self.abort_function():
                        raise self.abort_exception()
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            return False
        except SystemExit:
            # Kodi is killing the screensaver — convert to clean abort
            raise self.abort_exception()

    def close(self):
        try:
            self.api_session.close()
        except:
            pass
        try:
            self.download_file_session.close()
        except:
            pass
