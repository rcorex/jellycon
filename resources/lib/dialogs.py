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


# Track the active ResumeDialog at module scope so external callers (e.g. Service.onPlayBackStarted)
# can dismiss any lingering dialog, and so two instances never stack in Kodi's window manager.
_active_resume_dialog = None


class ResumeDialog(xbmcgui.WindowXMLDialog):
    # Return code for getResumeAction(): -1 = cancelled, 0 = resume from timestamp, 1 = start from beginning
    resumePlay = -1
    resumeTimeStamp = ""
    action_exitkeys_id = None

    def __init__(self, *args, **kwargs):
        global _active_resume_dialog
        # Close any previously active ResumeDialog so duplicate instances never stack
        if _active_resume_dialog is not None and _active_resume_dialog is not self:
            try:
                _active_resume_dialog.close()
            except Exception:
                pass
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        log.debug("ResumeDialog INITIALISED")
        self.resumePlay = -1
        self._closed = False
        _active_resume_dialog = self

    def doModal(self):
        global _active_resume_dialog
        # Guard against opening a dialog that was already closed before doModal() was reached
        if getattr(self, "_closed", False):
            log.debug("ResumeDialog: doModal() skipped because dialog is already closed")
            return
        try:
            super(ResumeDialog, self).doModal()
        finally:
            # Clear module-level reference on modal exit unless a newer instance already replaced it
            if _active_resume_dialog is self:
                _active_resume_dialog = None

    def onInit(self):
        # Register standard exit actions (10 = ACTION_PREVIOUS_MENU, 13 = ACTION_STOP)
        self.action_exitkeys_id = [10, 13]
        # Control 3010: "Resume from HH:MM:SS" button; Control 3011: "Start from beginning" button
        self.getControl(3010).setLabel(self.resumeTimeStamp)
        self.getControl(3011).setLabel(translate_string(30237))

    def onFocus(self, controlId):
        pass

    def doAction(self, actionID):
        pass

    def onAction(self, action):
        # Explicitly handle Back / Previous Menu / Stop so the dialog closes cleanly with resumePlay = -1,
        # signaling the caller to abort playback rather than starting from the beginning.
        if action.getId() in (10, 13, 92):  # ACTION_PREVIOUS_MENU, ACTION_STOP, ACTION_NAV_BACK
            self.close()

    def onClick(self, controlID):
        # Ignore duplicate clicks or key-repeats while the dialog is already closing
        if getattr(self, "_closed", False):
            return

        if controlID == 3010:
            # User chose to resume from the saved timestamp
            self.resumePlay = 0
            self.close()
        elif controlID == 3011:
            # User chose to start playback from the beginning
            self.resumePlay = 1
            self.close()

    def close(self):
        global _active_resume_dialog
        if _active_resume_dialog is self:
            _active_resume_dialog = None
        # Mark closed before calling super().close() to block any concurrent onClick/doModal calls
        self._closed = True
        try:
            super(ResumeDialog, self).close()
        except Exception as e:
            log.error("ResumeDialog: super().close() error: {0}".format(e))

    @classmethod
    def close_active(cls):
        # Allows external callers (e.g. playback start events) to dismiss any lingering ResumeDialog
        global _active_resume_dialog
        dialog = _active_resume_dialog
        _active_resume_dialog = None
        if dialog is not None:
            log.debug("ResumeDialog: close_active() closing active dialog")
            try:
                dialog.close()
            except Exception as e:
                log.error("ResumeDialog: close_active() error: {0}".format(e))

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
    # Automatically dismisses PlayNextDialog after inactivity or when playback state changes,
    # preventing a modal WindowXMLDialog from locking remote input focus.
    def __init__(self, parent, timeout=20, initial_playing=False, initial_file=None):
        super(PlayNextAutoClose, self).__init__()
        self.parent_dialog = parent
        self.stop_thread = threading.Event()
        self.last_interaction = time.time()
        self.timeout = timeout
        # Track whether playback was already active when the dialog opened (in-playback overlay vs. post-playback)
        self.initial_playing = initial_playing
        self.initial_file = initial_file
        # Daemonize so an orphaned timer thread can never block Kodi shutdown
        self.daemon = True

    def _should_close_for_playback(self, player):
        is_playing = player.isPlaying()
        if not self.initial_playing and is_playing:
            # Post-playback prompt was open when playback of the next item started
            log.debug("PlayNextAutoClose: playback started while post-playback dialog open, closing")
            return True
        if self.initial_playing:
            if not is_playing:
                # Playback stopped while the in-playback overlay was open
                log.debug("PlayNextAutoClose: playback stopped while overlay open, closing")
                return True
            try:
                current_file = player.getPlayingFile()
            except Exception:
                # Ignore transient player errors while Kodi transitions between streams
                current_file = None
            if self.initial_file and current_file and current_file != self.initial_file:
                # Playing file changed in-place (e.g. playlist or auto-advance to next episode)
                log.debug("PlayNextAutoClose: playing file changed while overlay open, closing")
                return True
        return False

    def run(self):
        log.debug("PlayNextAutoClose: started (initial_playing={0}, timeout={1}s)".format(
            self.initial_playing, self.timeout))
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        while not monitor.abortRequested() and not self.stop_thread.is_set():
            dlg = self.parent_dialog
            if dlg is None or getattr(dlg, "_closed", False):
                break

            if self._should_close_for_playback(player):
                dlg.close()
                break

            time_since_last = time.time() - self.last_interaction
            if time_since_last > self.timeout:
                log.debug("PlayNextAutoClose: timeout reached ({0}s), closing".format(self.timeout))
                dlg.close()
                break

            if monitor.waitForAbort(1):
                break

        # Drop reference to the dialog to avoid keeping C++ WindowXMLDialog alive past close
        self.parent_dialog = None
        log.debug("PlayNextAutoClose: exited")

    def set_last(self):
        # Reset inactivity timer whenever the user navigates within the dialog
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
        # Close any previously active PlayNextDialog so two instances never stack in Kodi's m_activeDialogs
        if _active_dialog is not None and _active_dialog is not self:
            try:
                _active_dialog.close()
            except Exception:
                pass
        log.debug("PlayNextDialog: __init__")
        # Initialize as WindowXMLDialog (not WindowXML) so Kodi treats this as a dialog
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
        # Guard against reopening an instance already dismissed by close_active() or PlayNextAutoClose
        if getattr(self, "_closed", False):
            log.debug("PlayNextDialog: show() skipped because dialog is already closed")
            return
        log.debug("PlayNextDialog: show()")
        self._start_auto_close()
        super(PlayNextDialog, self).show()

    def doModal(self):
        global _active_dialog
        # Guard against entering the modal loop on an already-closed instance
        if getattr(self, "_closed", False):
            log.debug("PlayNextDialog: doModal() skipped because dialog is already closed")
            return
        log.debug("PlayNextDialog: doModal() enter")
        self.is_modal = True
        self._start_auto_close()
        try:
            super(PlayNextDialog, self).doModal()
        finally:
            log.debug("PlayNextDialog: doModal() exit")
            self.is_modal = False
            # Clean up auto-close thread and active reference even if closed externally
            if self.auto_close_thread:
                self.auto_close_thread.stop()
                self.auto_close_thread = None
            if _active_dialog is self:
                _active_dialog = None

    def onInit(self):
        log.debug("PlayNextDialog: onInit (is_modal={0})".format(self.is_modal))
        self.action_exitkeys_id = [10, 13]

        if self.episode_info is not None:
            try:
                index = self.episode_info.get("IndexNumber")
                if index is None:
                    index = -1
                # Coalesce None to empty string or default to prevent Kodi deprecation warnings/errors
                series_name = self.episode_info.get("SeriesName") or ""
                next_epp_name = "Episode %02d - (%s)" % (index, self.episode_info.get("Name") or "n/a")

                # Control 3011: series title label; Control 3012: next episode label
                self.getControl(3011).setLabel(series_name)
                self.getControl(3012).setLabel(next_epp_name)
            except Exception as e:
                log.debug("PlayNextDialog: error setting labels: {0}".format(e))

        # Ensure auto-close thread is running even if opened via a non-overridden path
        self._start_auto_close()

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("PlayNextDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        action_id = action.getId()
        log.debug("PlayNextDialog: onAction: {0} (is_modal={1})".format(action_id, self.is_modal))

        # Keep modal focus only for 4-way navigation and Select (Left=1, Right=2, Up=3, Down=4, Select=7)
        if action_id in (1, 2, 3, 4, 7):
            if self.auto_close_thread:
                self.auto_close_thread.set_last()
            return

        # Any other action (Back, Previous Menu, Stop, Play/Pause, OSD, Info, etc.) dismisses
        # the dialog immediately so it never traps remote control input during video playback.
        self.close()

        # Forward player/OSD actions to Kodi since the modal dialog intercepted the key press
        if action_id == 13:  # ACTION_STOP
            xbmc.executebuiltin("PlayerControl(Stop)")
        elif action_id in (12, 68, 79, 229):  # ACTION_PAUSE, ACTION_PLAY, ACTION_PLAYER_PLAY, ACTION_PLAYER_PLAYPAUSE
            xbmc.executebuiltin("PlayerControl(Play)")
        elif action_id == 24:  # ACTION_SHOW_OSD
            xbmc.executebuiltin("ActivateWindow(videoosd)")
        elif action_id == 11:  # ACTION_SHOW_INFO
            xbmc.executebuiltin("Action(Info)")

    def onClick(self, control_id):
        # Ignore duplicate clicks or key-repeats while the dialog is already closing
        if getattr(self, "_closed", False):
            return
        log.debug("PlayNextDialog: onClick: {0}".format(control_id))
        if control_id == 3013:  # "Play Next" button
            log.debug("PlayNextDialog: Play Next Episode")
            # Mark play_called = True so prompt_for_stop_actions skips Container.Refresh
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
        elif control_id == 3014:  # "Close" button
            self.close()

    def set_episode_info(self, info):
        self.episode_info = info

    def get_play_called(self):
        return self.play_called

    def close(self):
        global _active_dialog
        log.debug("PlayNextDialog: close() called (_closed={0}, is_modal={1})".format(
            getattr(self, "_closed", False), self.is_modal))
        if self.auto_close_thread:
            self.auto_close_thread.stop()
            self.auto_close_thread = None
        if _active_dialog is self:
            _active_dialog = None
        # Mark closed before super().close() to block concurrent onClick/doModal/auto-close calls
        self._closed = True
        try:
            super(PlayNextDialog, self).close()
        except Exception as e:
            log.error("PlayNextDialog: super().close() error: {0}".format(e))

    @classmethod
    def close_active(cls):
        # Allows external callers (e.g. playback start or service stop) to dismiss any open dialog
        global _active_dialog
        dialog = _active_dialog
        _active_dialog = None
        if dialog is not None:
            log.debug("PlayNextDialog: close_active() closing active dialog")
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
