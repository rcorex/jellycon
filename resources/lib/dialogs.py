from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import threading
import time

import xbmcgui
import xbmc


from .lazylogger import LazyLogger
from .utils import seconds_to_ticks, ticks_to_seconds, translate_string, send_event_notification

log = LazyLogger(__name__)


class BitrateDialog(xbmcgui.WindowXMLDialog):

    slider_control = None
    bitrate_label = None
    initial_bitrate_value = 0
    selected_transcode_value = 0

    def __init__(self, *args, **kwargs):
        log.debug("BitrateDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("ActionMenu: onInit")
        self.action_exitkeys_id = [10, 13]

        self.slider_control = self.getControl(3000)
        self.slider_control.setInt(self.initial_bitrate_value, 400, 100, 15000)

        self.bitrate_label = self.getControl(3030)
        bitrate_label_string = str(self.slider_control.getInt()) + " Kbs"
        self.bitrate_label.setLabel(bitrate_label_string)
        self.getControl(3011).setLabel(translate_string(30314))

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("ActionMenu: onMessage: {0}".format(message))

    def onAction(self, action):

        bitrate_label_string = str(self.slider_control.getInt()) + " Kbs"
        self.bitrate_label.setLabel(bitrate_label_string)

        if action.getId() == 10:  # ACTION_PREVIOUS_MENU
            self.close()
        elif action.getId() == 92:  # ACTION_NAV_BACK
            self.close()
        elif action.getId() == 7:  # ENTER
            self.selected_transcode_value = self.slider_control.getInt()
            self.close()

    def onClick(self, control_id):
        if control_id == 3000:
            log.debug("ActionMenu: Selected Item: {0}".format(control_id))


class ResumeDialog(xbmcgui.WindowXMLDialog):
    resumePlay = -1
    resumeTimeStamp = ""
    action_exitkeys_id = None

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        log.debug("ResumeDialog INITIALISED")

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        self.getControl(3010).setLabel(self.resumeTimeStamp)
        self.getControl(3011).setLabel(translate_string(30237))

    def onFocus(self, controlId):
        pass

    def doAction(self, actionID):
        pass

    def onClick(self, controlID):

        if controlID == 3010:
            self.resumePlay = 0
            self.close()
        if controlID == 3011:
            self.resumePlay = 1
            self.close()

    def setResumeTime(self, timeStamp):
        self.resumeTimeStamp = timeStamp

    def getResumeAction(self):
        return self.resumePlay


class SafeDeleteDialog(xbmcgui.WindowXMLDialog):

    confirm = False
    message = "Demo Message"
    heading = "Demo Heading"
    action_exitkeys_id = None

    def __init__(self, *args, **kwargs):
        log.debug("SafeDeleteDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("SafeDeleteDialog: onInit")
        self.action_exitkeys_id = [10, 13]

        message_control = self.getControl(3)
        message_control.setText(self.message)

        message_control = self.getControl(4)
        message_control.setLabel(self.heading)

    def onFocus(self, controlId):
        pass

    def doAction(self, actionID):
        pass

    def onMessage(self, message):
        log.debug("SafeDeleteDialog: onMessage: {0}".format(message))

    def onAction(self, action):

        if action.getId() == 10:  # ACTION_PREVIOUS_MENU
            self.close()
        elif action.getId() == 92:  # ACTION_NAV_BACK
            self.close()
        else:
            log.debug("SafeDeleteDialog: onAction: {0}".format(action.getId()))

    def onClick(self, controlID):
        if controlID == 1:
            self.confirm = True
            self.close()
        elif controlID == 2:
            self.confirm = False
            self.close()


class PlayNextAutoClose(threading.Thread):
    # Automatically dismisses dialog after timeout or when playback begins,
    # preventing modal dialog loop from locking input focus.
    def __init__(self, parent, timeout=20):
        super(PlayNextAutoClose, self).__init__()
        self.parent_dialog = parent
        self.stop_thread = threading.Event()
        self.last_interaction = time.time()
        self.timeout = timeout
        self.daemon = True

    def run(self):
        log.debug("PlayNextAutoClose Running")
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        while not monitor.abortRequested() and not self.stop_thread.is_set():
            # If dialog was opened modally after playback ended and playback of next item begins,
            # close dialog so Kodi GUI returns input focus to the player.
            if self.parent_dialog and self.parent_dialog.is_modal and player.isPlaying():
                log.debug("PlayNextAutoClose: playback detected while dialog is modal, closing")
                self.parent_dialog.close()
                break

            time_since_last = time.time() - self.last_interaction
            if time_since_last > self.timeout:
                log.debug("PlayNextAutoClose: timeout reached ({0}s), closing".format(self.timeout))
                if self.parent_dialog:
                    self.parent_dialog.close()
                break

            if monitor.waitForAbort(1):
                break

        self.parent_dialog = None
        log.debug("PlayNextAutoClose Exited")

    def set_last(self):
        self.last_interaction = time.time()

    def stop(self):
        self.stop_thread.set()


# Track the active PlayNextDialog at module scope. Kodi's xbmcgui C++ extension classes
# disallow modifying class-level attributes at runtime (raising AttributeError).
_active_dialog = None


class PlayNextDialog(xbmcgui.WindowXMLDialog):

    action_exitkeys_id = None
    episode_info = None
    play_called = False
    auto_close_thread = None
    is_modal = False

    def __init__(self, *args, **kwargs):
        global _active_dialog
        log.debug("PlayNextDialog: __init__")
        # Initialize as WindowXMLDialog (not WindowXML) to ensure Kodi treats this as a dialog
        # with proper modal stacking and focus restoration on close.
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        self.play_called = False
        self.is_modal = False
        self._closed = False
        self.auto_close_thread = None
        _active_dialog = self

    def doModal(self):
        global _active_dialog
        self.is_modal = True
        try:
            super(PlayNextDialog, self).doModal()
        finally:
            self.is_modal = False
            # Clean up auto-close thread and active reference even if closed externally
            if self.auto_close_thread:
                self.auto_close_thread.stop()
                self.auto_close_thread = None
            if _active_dialog is self:
                _active_dialog = None

    def onInit(self):
        log.debug("PlayNextDialog: onInit")
        self.action_exitkeys_id = [10, 13]

        if self.episode_info is not None:
            try:
                index = self.episode_info.get("IndexNumber")
                if index is None:
                    index = -1
                # Coalesce None to empty string or default to prevent Kodi deprecation warnings/errors
                series_name = self.episode_info.get("SeriesName") or ""
                next_epp_name = "Episode %02d - (%s)" % (index, self.episode_info.get("Name") or "n/a")

                self.getControl(3011).setLabel(series_name)
                self.getControl(3012).setLabel(next_epp_name)
            except Exception as e:
                log.debug("PlayNextDialog: error setting labels: {0}".format(e))

        # Start auto-close thread to guard against modal dialog hanging indefinitely
        if self.auto_close_thread is None:
            self.auto_close_thread = PlayNextAutoClose(self, timeout=20)
            self.auto_close_thread.start()

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("PlayNextDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        if self.auto_close_thread:
            self.auto_close_thread.set_last()

        if action.getId() in (10, 92):  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
            self.close()
        else:
            log.debug("PlayNextDialog: onAction: {0}".format(action.getId()))

    def onClick(self, control_id):
        if control_id == 3013:
            log.debug("PlayNextDialog: Play Next Episode")
            # Mark play_called = True so caller knows playback was initiated and skips Container.Refresh
            self.play_called = True
            self.close()
            next_item_id = self.episode_info.get("Id") if self.episode_info else None
            if next_item_id:
                log.debug("Playing Next Episode: {0}".format(next_item_id))
                play_info = {}
                play_info["item_id"] = next_item_id
                play_info["auto_resume"] = "-1"
                play_info["force_transcode"] = False
                send_event_notification("jellycon_play_action", play_info)
        elif control_id == 3014:
            self.close()

    def set_episode_info(self, info):
        self.episode_info = info

    def get_play_called(self):
        return self.play_called

    def close(self):
        global _active_dialog
        if self.auto_close_thread:
            self.auto_close_thread.stop()
            self.auto_close_thread = None
        if _active_dialog is self:
            _active_dialog = None
        if not getattr(self, "_closed", False):
            self._closed = True
            try:
                super(PlayNextDialog, self).close()
            except Exception:
                pass

    @classmethod
    def close_active(cls):
        # Allows external callers (e.g. playback start events) to dismiss any open dialog
        global _active_dialog
        dialog = _active_dialog
        _active_dialog = None
        if dialog is not None:
            log.debug("PlayNextDialog: closing active dialog")
            try:
                dialog.close()
            except Exception:
                pass


class SkipDialog(xbmcgui.WindowXMLDialog):

    action_exitkeys_id = None
    media_id = None
    start = None
    end = None

    has_been_dismissed_or_skipped = False

    def __init__(self, *args, **kwargs):
        log.debug("SkipDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("SkipDialog: onInit")
        self.action_exitkeys_id = [10, 13]

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("SkipDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        log.debug("SkipDialog: onAction: {0}".format(action.getId()))
        if action.getId() == 10 or action.getId() == 92:  # ACTION_PREVIOUS_MENU & ACTION_NAV_BACK
            log.debug("SkipDialog: dismissing dialog so it does not open again")
            self.has_been_dismissed_or_skipped = True
            self.close()

    def onClick(self, control_id):
        log.debug("SkipDialog: onClick: {0}".format(control_id))
        player = xbmc.Player()
        current_ticks = seconds_to_ticks(player.getTime())
        if self.start is not None and self.end is not None and current_ticks >= self.start and current_ticks <= self.end:
            log.debug("SkipDialog: skipping segment because current ticks ({0}) is in range".format(current_ticks))
            # If click during segment, skip it
            player.seekTime(ticks_to_seconds(self.end))
            # mark dialog as skipped to avoid opening again
            self.has_been_dismissed_or_skipped = True
        self.close()

    def get_play_called(self):
        return self.play_called

    def is_button_shown(self):
        try:
            self.getFocus()
            return True
        except Exception:
            return False
