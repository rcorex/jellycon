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
    # Automatically dismisses dialog after timeout or when playback state changes,
    # preventing WindowXMLDialog from locking remote input focus.
    def __init__(self, parent, timeout=20, initial_playing=False, initial_file=None):
        super(PlayNextAutoClose, self).__init__()
        self.parent_dialog = parent
        self.stop_thread = threading.Event()
        self.last_interaction = time.time()
        self.timeout = timeout
        self.initial_playing = initial_playing
        self.initial_file = initial_file
        self.daemon = True

    def run(self):
        log.info("PlayNextAutoClose: started (initial_playing={0}, timeout={1}s)".format(
            self.initial_playing, self.timeout))
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        while not monitor.abortRequested() and not self.stop_thread.is_set():
            dlg = self.parent_dialog
            if dlg is None or getattr(dlg, "_closed", False):
                break

            is_playing = player.isPlaying()
            if not self.initial_playing and is_playing:
                # Dialog was opened after playback ended and playback of next item started
                log.info("PlayNextAutoClose: playback started while post-playback dialog open, closing")
                dlg.close()
                break
            elif self.initial_playing:
                if not is_playing:
                    # Playback stopped while in-playback overlay was open
                    log.info("PlayNextAutoClose: playback stopped while overlay open, closing")
                    dlg.close()
                    break
                try:
                    current_file = player.getPlayingFile()
                except Exception:
                    current_file = None
                if self.initial_file and current_file and current_file != self.initial_file:
                    # Playing file changed in-place (next episode started)
                    log.info("PlayNextAutoClose: playing file changed while overlay open, closing")
                    dlg.close()
                    break

            time_since_last = time.time() - self.last_interaction
            if time_since_last > self.timeout:
                log.info("PlayNextAutoClose: timeout reached ({0}s), closing".format(self.timeout))
                dlg.close()
                break

            if monitor.waitForAbort(1):
                break

        self.parent_dialog = None
        log.info("PlayNextAutoClose: exited")

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
        # Close any previously active PlayNextDialog so two instances never stack in m_activeDialogs
        if _active_dialog is not None and _active_dialog is not self:
            try:
                _active_dialog.close()
            except Exception:
                pass
        log.info("PlayNextDialog: __init__")
        # Initialize as WindowXMLDialog (not WindowXML) to ensure Kodi treats this as a dialog
        # with proper modal stacking and focus restoration on close.
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        self.play_called = False
        self.is_modal = False
        self._closed = False
        self.auto_close_thread = None
        _active_dialog = self

    def _start_auto_close(self):
        if self.auto_close_thread is None:
            player = xbmc.Player()
            is_playing = player.isPlaying()
            playing_file = None
            if is_playing:
                try:
                    playing_file = player.getPlayingFile()
                except Exception:
                    playing_file = None
            self.auto_close_thread = PlayNextAutoClose(
                self, timeout=20, initial_playing=is_playing, initial_file=playing_file
            )
            self.auto_close_thread.start()

    def show(self):
        if getattr(self, "_closed", False):
            log.info("PlayNextDialog: show() skipped because dialog is already closed")
            return
        log.info("PlayNextDialog: show()")
        self._start_auto_close()
        super(PlayNextDialog, self).show()

    def doModal(self):
        global _active_dialog
        if getattr(self, "_closed", False):
            log.info("PlayNextDialog: doModal() skipped because dialog is already closed")
            return
        log.info("PlayNextDialog: doModal() enter")
        self.is_modal = True
        self._start_auto_close()
        try:
            super(PlayNextDialog, self).doModal()
        finally:
            log.info("PlayNextDialog: doModal() exit")
            self.is_modal = False
            # Clean up auto-close thread and active reference even if closed externally
            if self.auto_close_thread:
                self.auto_close_thread.stop()
                self.auto_close_thread = None
            if _active_dialog is self:
                _active_dialog = None

    def onInit(self):
        log.info("PlayNextDialog: onInit (is_modal={0})".format(self.is_modal))
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

        # Ensure auto-close thread is running
        self._start_auto_close()

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("PlayNextDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        action_id = action.getId()
        log.info("PlayNextDialog: onAction: {0} (is_modal={1})".format(action_id, self.is_modal))

        # Navigation actions within the 2-button dialog (Left=1, Right=2, Up=3, Down=4, Select=7)
        if action_id in (1, 2, 3, 4, 7):
            if self.auto_close_thread:
                self.auto_close_thread.set_last()
            return

        # Back / Previous Menu / Stop / Play / Pause / OSD / Info:
        # Close the dialog so it never traps remote control input during video playback.
        self.close()

        # Forward playback control actions to Kodi if the user pressed them while the overlay was visible
        if action_id == 13:  # ACTION_STOP
            xbmc.executebuiltin("PlayerControl(Stop)")
        elif action_id in (12, 68, 79, 229):  # ACTION_PAUSE, ACTION_PLAY, ACTION_PLAYER_PLAY, ACTION_PLAYER_PLAYPAUSE
            xbmc.executebuiltin("PlayerControl(Play)")
        elif action_id == 24:  # ACTION_SHOW_OSD
            xbmc.executebuiltin("ActivateWindow(videoosd)")
        elif action_id == 11:  # ACTION_SHOW_INFO
            xbmc.executebuiltin("Action(Info)")

    def onClick(self, control_id):
        log.info("PlayNextDialog: onClick: {0}".format(control_id))
        if control_id == 3013:
            log.info("PlayNextDialog: Play Next Episode")
            # Mark play_called = True so caller knows playback was initiated and skips Container.Refresh
            self.play_called = True
            self.close()
            next_item_id = self.episode_info.get("Id") if self.episode_info else None
            if next_item_id:
                log.info("Playing Next Episode: {0}".format(next_item_id))
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
        log.info("PlayNextDialog: close() called (_closed={0}, is_modal={1})".format(
            getattr(self, "_closed", False), self.is_modal))
        if self.auto_close_thread:
            self.auto_close_thread.stop()
            self.auto_close_thread = None
        if _active_dialog is self:
            _active_dialog = None
        self._closed = True
        try:
            super(PlayNextDialog, self).close()
        except Exception as e:
            log.error("PlayNextDialog: super().close() error: {0}".format(e))

    @classmethod
    def close_active(cls):
        # Allows external callers (e.g. playback start events) to dismiss any open dialog
        global _active_dialog
        dialog = _active_dialog
        _active_dialog = None
        if dialog is not None:
            log.info("PlayNextDialog: close_active() closing active dialog")
            try:
                dialog.close()
            except Exception as e:
                log.error("PlayNextDialog: close_active() error: {0}".format(e))


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
