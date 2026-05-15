# Only expose ImmichAPI and log/notify by default, otherwise everone needs stuff im modules directory
from .helpers import log
from .helpers import notify
from .immichapi import ImmichAPI

# DatabaseAPI is optional — import only when requested
def __getattr__(name):
    if name == "DatabaseAPI":
        from .databaseapi import DatabaseAPI
        return DatabaseAPI
    raise AttributeError(name)
