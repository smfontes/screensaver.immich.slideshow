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

# This script queries the Immich API to get a list of album names.
# A dialog is provided to select albums for the screensaver.

import os
import sys
import json
from pathlib import Path
import xbmc
import xbmcvfs
import xbmcaddon
import xbmcgui
from services import ImmichAPI
from services import log, notify

DONE = 20177
ALBUM_NAMES = 30810
NO_ALBUMS_FOUND = 30820
ALBUMS_SAVE_FAILED = 30830
ALBUMS_SELECTED = 30840

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_USERDATA_FOLDER = Path(xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}"))
ALBUMS_FILE = ADDON_USERDATA_FOLDER / "selected_albums.json"

def dialog_multiselect(title, items, preselect=None):
    dialog = xbmcgui.Dialog()
    # Kodi 21+ native multiselect
    if hasattr(dialog, "multiselect"):
        return dialog.multiselect(title, items, preselect=preselect)
    # Fallback for Kodi 20 and older
    selected = set(preselect or [])
    while True:
        display = []
        for i, label in enumerate(items):
            prefix = "[X] " if i in selected else "[ ] "
            display.append(prefix + label)
        # Add explicit "Done" entry that is ALWAYS visible
        display.append(ADDON.getLocalizedString(DONE))
        idx = dialog.select(title, display)
        if idx < 0:
            # User pressed Cancel
            return None
        if idx == len(display) - 1:
            # User selected "Done"
            break
        # Toggle selection
        if idx in selected:
            selected.remove(idx)
        else:
            selected.add(idx)
    return sorted(selected)

def save_albums(selected):
    albums = {"albums": [{"albumName": a.get("albumName", ""), "id": a["id"]} for a in selected]}
    data = json.dumps(albums, ensure_ascii=False)
    ALBUMS_FILE.write_text(data, encoding="utf-8")

def load_selected_albums():
    if not ALBUMS_FILE.exists():
        return []
    try:
        content = ALBUMS_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        return data.get("albums", [])
    except Exception as e:
        utils.log(f"Failed to load existing albums list: {type(e).__name__} {str(e)}")
        return []

def main():
    ADDON_USERDATA_FOLDER.mkdir(parents=True, exist_ok=True)
    api_key = ADDON.getSetting("APIKey")
    url = ADDON.getSetting("URL")
    api = ImmichAPI(api_key, url, Exception, lambda: False)
    albums = api.get_albums()
    if albums is None:
        return
    if len(albums) == 0:
        notify(ADDON.getLocalizedString(NO_ALBUMS_FOUND))
        return
    albums.sort(key=lambda a: (a.get("albumName") or "").lower())
    labels = [f'{a.get("albumName", "")} ({a.get("assetCount", 0)})'for a in albums]
    selected_albums = load_selected_albums()
    selected_ids = {s.get("id") for s in selected_albums}
    preselect = [i for i, a in enumerate(albums) if a.get("id") in selected_ids]
    selected_indices = dialog_multiselect(ADDON.getLocalizedString(ALBUM_NAMES), labels, preselect=preselect)
    if selected_indices is None:
        return

    selected_albums = [albums[i] for i in selected_indices]
    try:
        save_albums(selected_albums)
        notify(f"{len(selected_albums)} {ADDON.getLocalizedString(ALBUMS_SELECTED)}","",xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        log(f"Failed to save albums list: {type(e).__name__} {str(e)}")
        notify(ADDON.getLocalizedString(ALBUMS_SAVE_FAILED), type(e).__name__)

if __name__ == "__main__":
    main()
