# -*- coding: utf-8 -*-
from six.moves.cPickle import dump, load
from os import W_OK, access, listdir, mkdir, rename, rmdir, stat
from os.path import abspath, basename, exists, isdir, isfile, join as pathjoin, normpath, pardir, realpath, split, splitext
from time import time

from enigma import eRCInput, eServiceCenter, eServiceReference, eSize, eTimer, iPlayableService, iServiceInformation, getPrevAsciiCode

import NavigationInstance
from RecordTimer import AFTEREVENT, RecordTimerEntry
from Components.ActionMap import ActionMap, HelpableActionMap, NumberActionMap
from Components.Button import Button
from Components.ChoiceList import ChoiceEntryComponent, ChoiceList
from Components.config import ConfigLocations, ConfigSelection, ConfigSelectionNumber, ConfigSet, ConfigSubsection, ConfigText, ConfigYesNo, config, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.DiskInfo import DiskInfo
from Components.Harddisk import harddiskmanager
from Components.Label import Label
from Components.MovieList import AUDIO_EXTENSIONS, DVD_EXTENSIONS, IMAGE_EXTENSIONS, MovieList, moviePlayState, resetMoviePlayState
from Components.Pixmap import MultiPixmap, Pixmap
from Components.PluginComponent import plugins
from Components.ServiceEventTracker import InfoBarBase, ServiceEventTracker
from Components.UsageConfig import preferredTimerPath
# from Components.Sources.Boolean import Boolean
from Components.Sources.ServiceEvent import ServiceEvent
from Components.Sources.StaticText import StaticText
try:
	from Plugins.Extensions import BlurayPlayer
except ImportError:
	print("[MovieSelection] Bluray Player is not installed.")
	BlurayPlayer = None
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.HelpMenu import HelpableScreen
import Screens.InfoBar
# from Screens.InfoBar import InfoBar
# from Screens.InfoBarGenerics import delResumePoint
from Screens.InputBox import PinInput
from Screens.LocationBox import MovieLocationBox
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.TagEditor import TagEditor
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Tools.BoundFunction import boundFunction
from Tools.CopyFiles import copyFiles, deleteFiles, moveFiles
from Tools.Directories import SCOPE_HDD, resolveFilename
from Tools.NumericalTextInput import MAP_SEARCH_UPCASE, NumericalTextInput
from Tools.Trashcan import TrashInfo, cleanAll, createTrashFolder, getTrashFolder

l_moviesort = [
	(str(MovieList.SORT_GROUPWISE), _("Recordings by date, other media by name"), 'Rec New-Old & A-Z'),
	(str(MovieList.SORT_RECORDED), _("By date, then by name"), 'New-Old, A-Z'),
	(str(MovieList.SORT_RECORDED_REVERSE), _("By reverse date, then by reverse name"), 'Old-New, Z-A'),
	(str(MovieList.SORT_ALPHANUMERIC), _("By name, then by date"), 'A-Z, New-Old'),
	(str(MovieList.SORT_ALPHANUMERIC_FLAT), _("Flat by name, then by date"), 'Flat A-Z, New-Old'),
	(str(MovieList.SORT_ALPHA_DATE_OLDEST_FIRST), _("By name, then by reverse date"), 'A-Z, Old-New'),
	(str(MovieList.SORT_ALPHAREV_DATE_NEWEST_FIRST), _("By reverse name, then by date"), 'Z-A, New-Old'),
	(str(MovieList.SORT_ALPHANUMERIC_REVERSE), _("By reverse name, then by reverse date"), 'Z-A, Old-New'),
	(str(MovieList.SORT_ALPHANUMERIC_FLAT_REVERSE), _("Flat by reverse name, then by reverse date"), 'Flat Z-A, Old-New'),
	(str(MovieList.SORT_DURATION_ALPHA), _("By duration, then by name"), 'Short-Long A-Z'),
	(str(MovieList.SORT_DURATIONREV_ALPHA), _("By reverse duration, then by name"), 'Long-Short A-Z'),
	(str(MovieList.SORT_SIZE_ALPHA), _("By file size, then by name"), 'Small-Large A-Z'),
	(str(MovieList.SORT_SIZEREV_ALPHA), _("By reverse file size, then by name"), 'Large-Small A-Z'),
	(str(MovieList.SORT_DESCRIPTION_ALPHA), _("By description, then by name"), 'Descr A-Z'),
	(str(MovieList.SORT_SHUFFLE), _("Shuffle"), "Shuffle")
]

l_desc = [
	(str(MovieList.SHOW_DESCRIPTION), _("Yes")),
	(str(MovieList.HIDE_DESCRIPTION), _("No"))]

# 4th item is the textual value set in UsageConfig.py
#
l_trashsort = [
	(str(MovieList.TRASHSORT_SHOWRECORD), _("delete time - show record time (Trash ONLY)"), "03/02/01", "show record time"),
	(str(MovieList.TRASHSORT_SHOWDELETE), _("delete time - show delete time (Trash ONLY)"), "03/02/01", "show delete time")
]

userDefinedActions = {
	"delete": _("Delete"),
	"move": _("Move"),
	"copy": _("Copy"),
	"reset": _("Reset"),
	"tags": _("Tags"),
	"createdir": _("Create directory"),
	"addbookmark": _("Add bookmark"),
	"bookmarks": _("Location"),
	"rename": _("Rename"),
	"gohome": _("Home"),
	"sort": _("Sort"),
	"sortby": _("Sort by"),
	"sortdefault": _("Sort by default"),
	"listtype": _("List type"),
	"preview": _("Preview"),
	"movieoff": _("On end of movie"),
	"movieoff_menu": _("On end of movie (As menu)")
}

config.movielist = ConfigSubsection()
config.movielist.last_videodir = ConfigText(default=resolveFilename(SCOPE_HDD))
config.movielist.last_timer_videodir = ConfigText(default=resolveFilename(SCOPE_HDD))
config.movielist.videodirs = ConfigLocations(default=[resolveFilename(SCOPE_HDD)])
config.movielist.last_selected_tags = ConfigSet([], default=[])
config.movielist.curentlyplayingservice = ConfigText()
config.movielist.fontsize = ConfigSelectionNumber(default=0, stepwidth=1, min=-20, max=20, wraparound=True)
config.movielist.itemsperpage = ConfigSelectionNumber(default=15, stepwidth=1, min=3, max=30, wraparound=True)
config.movielist.useslim = ConfigYesNo(default=False)
config.movielist.use_fuzzy_dates = ConfigYesNo(default=True)
# config.movielist.moviesort = ConfigInteger(default=MovieList.SORT_GROUPWISE)
config.movielist.moviesort = ConfigSelection(default=str(MovieList.SORT_GROUPWISE), choices=[(x[0], x[1]) for x in l_moviesort])
# config.movielist.description = ConfigInteger(default=MovieList.SHOW_DESCRIPTION)
# cfg.description = ConfigYesNo(default=(config.movielist.description.value != MovieList.HIDE_DESCRIPTION))
config.movielist.description = ConfigSelection(default=str(MovieList.SHOW_DESCRIPTION), choices=l_desc)
config.movielist.settings_per_directory = ConfigYesNo(default=True)
config.movielist.perm_sort_changes = ConfigYesNo(default=True)
config.movielist.stop_service = ConfigYesNo(default=False)
config.movielist.play_audio_internal = ConfigYesNo(default=True)
config.movielist.root = ConfigSelection(default="/media", choices=["/", "/media", "/media/hdd", "/media/hdd/movie", "/media/usb", "/media/usb/movie"])
config.movielist.hide_extensions = ConfigYesNo(default=False)
config.movielist.hide_images = ConfigYesNo(default=True)
config.movielist.add_bookmark = ConfigYesNo(default=True)
config.movielist.show_underlines = ConfigYesNo(default=False)
config.movielist.show_live_tv_in_movielist = ConfigYesNo(default=True)
config.movielist.btn_red = ConfigSelection(default="delete", choices=userDefinedActions)
config.movielist.btn_green = ConfigSelection(default="move", choices=userDefinedActions)
config.movielist.btn_yellow = ConfigSelection(default="bookmarks", choices=userDefinedActions)
config.movielist.btn_blue = ConfigSelection(default="sortby", choices=userDefinedActions)
config.movielist.btn_redlong = ConfigSelection(default="rename", choices=userDefinedActions)
config.movielist.btn_greenlong = ConfigSelection(default="copy", choices=userDefinedActions)
config.movielist.btn_yellowlong = ConfigSelection(default="tags", choices=userDefinedActions)
config.movielist.btn_bluelong = ConfigSelection(default="sortdefault", choices=userDefinedActions)
config.movielist.btn_radio = ConfigSelection(default="tags", choices=userDefinedActions)
config.movielist.btn_tv = ConfigSelection(default="gohome", choices=userDefinedActions)
config.movielist.btn_text = ConfigSelection(default="movieoff", choices=userDefinedActions)
config.movielist.btn_F1 = ConfigSelection(default="movieoff_menu", choices=userDefinedActions)
config.movielist.btn_F2 = ConfigSelection(default="preview", choices=userDefinedActions)
config.movielist.btn_F3 = ConfigSelection(default="/media", choices=userDefinedActions)

userDefinedButtons = None
last_selected_dest = []
preferredTagEditor = None


def defaultMoviePath():
	result = config.usage.default_path.value
	if not isdir(result):
		from Tools import Directories
		return Directories.defaultRecordingLocation()
	return result


def setPreferredTagEditor(tageditor):  # Place holder function for legacy plugins yet to use the new embedded TagEditor.
	return


def getPreferredTagEditor():  # Place holder function for legacy plugins yet to use the new embedded TagEditor.
	return None


def isTrashFolder(ref):
	if not config.usage.movielist_trashcan.value or not ref.flags & eServiceReference.mustDescent:
		return False
	return realpath(ref.getPath()).endswith(".Trash") or realpath(ref.getPath()).endswith(".Trash/")


def isInTrashFolder(ref):
	if not config.usage.movielist_trashcan.value or not ref.flags & eServiceReference.mustDescent:
		return False
	path = realpath(ref.getPath())
	return path.startswith(getTrashFolder(path))


def isSimpleFile(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return (item[0].flags & eServiceReference.mustDescent) == 0


def isFolder(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return (item[0].flags & eServiceReference.mustDescent) != 0


def canMove(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return True


canDelete = canMove
canCopy = canMove
canRename = canMove


def createMoveList(serviceref, dest):
	# normpath is to remove the trailing "/" from directories
	ext_ts = "%s.ts" % serviceref
	src = isinstance(serviceref, str) and "%s.ts" % serviceref or normpath(serviceref.getPath()) if exists(ext_ts) else isinstance(serviceref, str) and "%s.stream" % serviceref or normpath(serviceref.getPath())
	srcPath, srcName = split(src)
	if normpath(srcPath) == dest:
		# Move file to itself is allowed, so we have to check it.
		raise Exception(_("Refusing to move to the same directory"))
	# Make a list of items to move.
	moveList = [(src, pathjoin(dest, srcName))]
	if isinstance(serviceref, str) or not serviceref.flags & eServiceReference.mustDescent:
		# Real movie, add extra files...
		srcBase = splitext(src)[0]
		baseName = split(srcBase)[1]
		eitName = "%s.eit" % srcBase
		if exists(eitName):
			moveList.append((eitName, pathjoin(dest, "%s.eit" % baseName)))
		baseName = split(src)[1]
		for ext in ("%s.ap", "%s.cuts", "%s.meta", "%s.sc"):
			candidate = ext % src
			if exists(candidate):
				moveList.append((candidate, pathjoin(dest, ext % baseName)))
	return moveList


def moveServiceFiles(serviceref, dest, name=None, allowCopy=True):
	moveList = createMoveList(serviceref, dest)
	# Try to "atomically" move these files
	movedList = []
	try:
		# print("[MovieSelection] Moving in background...")
		# start with the smaller files, do the big one later.
		moveList.reverse()
		if name is None:
			name = split(moveList[-1][0])[1]
		moveFiles(moveList, name)
	except Exception as e:
		print("[MovieSelection] Failed move:", e)
		# rethrow exception
		raise


def copyServiceFiles(serviceref, dest, name=None):
	# current should be "ref" type, dest a simple path string
	moveList = createMoveList(serviceref, dest)
	# Try to "atomically" move these files
	movedList = []
	try:
		# print("[MovieSelection] Copying in background...")
		# start with the smaller files, do the big one later.
		moveList.reverse()
		if name is None:
			name = split(moveList[-1][0])[1]
		copyFiles(moveList, name)
	except Exception as e:
		print("[MovieSelection] Failed copy:", e)
		# rethrow exception
		raise


# Appends possible destinations to the bookmarks object. Appends tuples
# in the form (description, path) to it.
#
def buildMovieLocationList(bookmarks):
	inlist = []
	for d in config.movielist.videodirs.value:
		d = normpath(d)
		bookmarks.append((d, d))
		inlist.append(d)
	for p in harddiskmanager.getMountedPartitions():
		d = normpath(p.mountpoint)
		if d in inlist:
			# improve shortcuts to mountpoints
			try:
				bookmarks[bookmarks.index((d, d))] = (p.tabbedDescription(), d)
			except:
				pass  # When already listed as some "friendly" name
		else:
			bookmarks.append((p.tabbedDescription(), d))
		inlist.append(d)
	for d in last_selected_dest:
		if d not in inlist:
			bookmarks.append((d, d))


class SelectionEventInfo:
	def __init__(self):
		self["Service"] = ServiceEvent()
		self.list.connectSelChanged(self.__selectionChanged)
		self.timer = eTimer()
		self.timer.callback.append(self.updateEventInfo)
		self.onShown.append(self.__selectionChanged)

	def __selectionChanged(self):
		if self.execing and self.settings["description"] == MovieList.SHOW_DESCRIPTION:
			self.timer.start(100, True)

	def updateEventInfo(self):
		serviceref = self.getCurrent()
		self["Service"].newService(serviceref)


class MovieSelection(Screen, HelpableScreen, SelectionEventInfo, InfoBarBase, ProtectedScreen):
	# SUSPEND_PAUSES actually means "please call my pauseService()"
	ALLOW_SUSPEND = Screen.SUSPEND_PAUSES

	def __init__(self, session, selectedmovie=None, timeshiftEnabled=False):
		Screen.__init__(self, session)
		if config.movielist.useslim.value:
			self.skinName = ["MovieSelectionSlim", "MovieSelection"]
		else:
			self.skinName = "MovieSelection"
		HelpableScreen.__init__(self)
		if not timeshiftEnabled:
			InfoBarBase.__init__(self)  # For ServiceEventTracker
		ProtectedScreen.__init__(self)

		self.setTitle(_("Movie selection"))
		self.protectContextMenu = True

		self.initUserDefinedActions()
		self.tags = {}
		if selectedmovie:
			self.selected_tags = config.movielist.last_selected_tags.value
		else:
			self.selected_tags = None
		self.selected_tags_ele = None
		self.nextInBackground = None

		self.movemode = False
		self.bouquet_mark_edit = False

		self.feedbackTimer = None
		self.pathselectEnabled = False

		self.numericalTextInput = NumericalTextInput(mapping=MAP_SEARCH_UPCASE)
		self["chosenletter"] = Label("")
		self["chosenletter"].visible = False

		self["waitingtext"] = Label(_("Please wait... Loading list..."))

		self.LivePlayTimer = eTimer()
		self.LivePlayTimer.timeout.get().append(self.LivePlay)

		self.filePlayingTimer = eTimer()
		self.filePlayingTimer.timeout.get().append(self.FilePlaying)

		self.playingInForeground = None
		# create optional description border and hide immediately
		self["DescriptionBorder"] = Pixmap()
		self["DescriptionBorder"].hide()

		if config.ParentalControl.servicepinactive.value:
			from Components.ParentalControl import parentalControl
			if not parentalControl.sessionPinCached and config.movielist.last_videodir.value and [x for x in config.movielist.last_videodir.value[1:].split("/") if x.startswith(".") and not x.startswith(".Trash")]:
				config.movielist.last_videodir.value = ""
		if not isdir(config.movielist.last_videodir.value):
			config.movielist.last_videodir.value = defaultMoviePath()
			config.movielist.last_videodir.save()
		self.setCurrentRef(config.movielist.last_videodir.value)

		self.settings = {
			"moviesort": config.movielist.moviesort.value,
			"description": config.movielist.description.value,
			"movieoff": config.usage.on_movie_eof.value
		}
		self.movieOff = self.settings["movieoff"]

		self["list"] = MovieList(None, sort_type=self.settings["moviesort"], descr_state=self.settings["description"])

		self.list = self["list"]
		self.selectedmovie = selectedmovie

		self.playGoTo = None  # 1 - preview next item / -1 - preview previous

		# Need list for init
		SelectionEventInfo.__init__(self)

		self["key_red"] = Button("")
		self["key_green"] = Button("")
		self["key_yellow"] = Button("")
		self["key_blue"] = Button("")
		self._updateButtonTexts()

		self["movie_off"] = MultiPixmap()
		self["movie_off"].hide()

		self["movie_sort"] = MultiPixmap()
		self["movie_sort"].hide()

		self["freeDiskSpace"] = self.diskinfo = DiskInfo(config.movielist.last_videodir.value, DiskInfo.FREE, update=False)
		self["TrashcanSize"] = self.trashinfo = TrashInfo(config.movielist.last_videodir.value, TrashInfo.USED, update=False)

		self["InfobarActions"] = HelpableActionMap(self, ["InfobarActions"], {
			"showMovies": (self.doPathSelect, _("Select the movie path")),
			"showRadio": (self.btn_radio, boundFunction(self.getinitUserDefinedActionsDescription, "btn_radio")),
			"showTv": (self.btn_tv, boundFunction(self.getinitUserDefinedActionsDescription, "btn_tv")),
			"showText": (self.btn_text, boundFunction(self.getinitUserDefinedActionsDescription, "btn_text"))
		}, prio=0)
		self["NumberActions"] = NumberActionMap(["NumberActions", "InputAsciiActions"], {
			"gotAsciiCode": self.keyAsciiCode,
			"0": self.keyNumberGlobal,
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal
		}, prio=0)
		self["playbackActions"] = HelpableActionMap(self, ["MoviePlayerActions"], {
			"leavePlayerOnExit": (self.abort, _("Exit movie list")),
			"leavePlayer": (self.playbackStop, _("Stop")),
			"moveNext": (self.playNext, _("Play next")),
			"movePrev": (self.playPrev, _("Play previous")),
			"channelUp": (self.moveToFirstOrFirstFile, _("Go to first movie or top of list")),
			"channelDown": (self.moveToLastOrFirstFile, _("Go to first movie or last item"))
		}, prio=0)
		self["MovieSelectionActions"] = HelpableActionMap(self, ["MovieSelectionActions"], {
			"contextMenu": (self.doContext, _("Menu")),
			"showEventInfo": (self.showEventInformation, _("Show event details"))
		}, prio=0)
		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"], {
			"red": (self.btn_red, boundFunction(self.getinitUserDefinedActionsDescription, "btn_red")),
			"green": (self.btn_green, boundFunction(self.getinitUserDefinedActionsDescription, "btn_green")),
			"yellow": (self.btn_yellow, boundFunction(self.getinitUserDefinedActionsDescription, "btn_yellow")),
			"blue": (self.btn_blue, boundFunction(self.getinitUserDefinedActionsDescription, "btn_blue")),
			"redlong": (self.btn_redlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_redlong")),
			"greenlong": (self.btn_greenlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_greenlong")),
			"yellowlong": (self.btn_yellowlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_yellowlong")),
			"bluelong": (self.btn_bluelong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_bluelong"))
		}, prio=0)
		self["FunctionKeyActions"] = HelpableActionMap(self, ["FunctionKeyActions"], {
			"f1": (self.btn_F1, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F1")),
			"f2": (self.btn_F2, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F2")),
			"f3": (self.btn_F3, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F3"))
		}, prio=0)
		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"], {
			"cancel": (self.abort, _("Exit movie list")),
			"ok": (self.itemSelected, _("Select movie"))
		}, prio=0)
		self["DirectionActions"] = HelpableActionMap(self, ["DirectionActions"], {
			"left": self.pageUp,
			"right": self.pageDown,
			"leftRepeated": self.pageUp,
			"rightRepeated": self.pageDown,
			"upUp": self.doNothing,
			"downUp": self.doNothing,
			"rightUp": self.doNothing,
			"leftUp": self.doNothing,
			"upRepeated": self.keyUp,
			"downRepeated": self.keyDown,
			"up": (self.keyUp, _("Go up the list")),
			"down": (self.keyDown, _("Go down the list"))
		}, prio=-2)

		tPreview = _("Preview")
		tFwd = "%s (%s)" % (_("skip forward"), tPreview)
		tBack = "%s (%s)" % (_("skip backward"), tPreview)
		sfwd = lambda: self.seekRelative(1, config.seek.selfdefined_46.value * 90000)
		ssfwd = lambda: self.seekRelative(1, config.seek.selfdefined_79.value * 90000)
		sback = lambda: self.seekRelative(-1, config.seek.selfdefined_46.value * 90000)
		ssback = lambda: self.seekRelative(-1, config.seek.selfdefined_79.value * 90000)
		self["SeekActions"] = HelpableActionMap(self, ["MovielistSeekActions"], {
			"playpauseService": (self.preview, _("Preview")),
			"seekFwd": (sfwd, tFwd),
			"seekFwdManual": (ssfwd, tFwd),
			"seekBack": (sback, tBack),
			"seekBackManual": (ssback, tBack)
		}, prio=5)
		self.onShown.append(self.onFirstTimeShown)
		self.onLayoutFinish.append(self.saveListsize)
		self.list.connectSelChanged(self.updateButtons)
		self.onClose.append(self.__onClose)
		NavigationInstance.instance.RecordTimer.on_state_change.append(self.list.updateRecordings)
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap={
			# iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
			iPlayableService.evStart: self.__serviceStarted,
			iPlayableService.evEOF: self.__evEOF,
			# iPlayableService.evSOF: self.__evSOF,
		})
		self.onExecBegin.append(self.asciiOn)
		config.misc.standbyCounter.addNotifier(self.standbyCountChanged, initial_call=False)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.movie_list.value

	def standbyCountChanged(self, value):
		path = self.getTitle().split(" /", 1)
		if path and len(path) > 1:
			if [x for x in path[1].split("/") if x.startswith(".") and not x.startswith(".Trash")]:
				moviepath = defaultMoviePath()
				if moviepath:
					config.movielist.last_videodir.value = defaultMoviePath()
					self.close(None)

	def unhideParentalServices(self):
		if self.protectContextMenu:
			self.session.openWithCallback(self.unhideParentalServicesCallback, PinInput, pinList=[config.ParentalControl.servicepin[0].value], triesEntry=config.ParentalControl.retries.servicepin, title=_("Enter the service pin"), windowTitle=_("Enter PIN code"))
		else:
			self.unhideParentalServicesCallback(True)

	def unhideParentalServicesCallback(self, answer):
		if answer:
			from Components.ParentalControl import parentalControl
			parentalControl.setSessionPinCached()
			parentalControl.hideBlacklist()
			self.reloadList()
		elif answer is not None:
			self.session.openWithCallback(self.close, MessageBox, _("The PIN code you entered is wrong."), MessageBox.TYPE_ERROR)

	def asciiOn(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmAscii)

	def asciiOff(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmNone)

	def initUserDefinedActions(self):
		global userDefinedButtons, userDefinedActions, config
		if userDefinedButtons is None:
			userDefinedActions = {
				"delete": _("Delete"),
				"move": _("Move"),
				"copy": _("Copy"),
				"reset": _("Reset"),
				"tags": _("Tags"),
				"createdir": _("Create directory"),
				"addbookmark": _("Add bookmark"),
				"bookmarks": _("Location"),
				"rename": _("Rename"),
				"gohome": _("Home"),
				"sort": _("Sort"),
				"sortby": _("Sort by"),
				"sortdefault": _("Sort by default"),
				"listtype": _("List type"),
				"preview": _("Preview"),
				"movieoff": _("On end of movie"),
				"movieoff_menu": _("On end of movie (as menu)")
			}
			for plugin in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
				userDefinedActions["@%s" % plugin.name] = plugin.description
			locations = []
			buildMovieLocationList(locations)
			for d, p in locations:
				if p and p.startswith("/"):
					userDefinedActions[p] = "%s: %s" % (_("Goto"), d)
			config.movielist.btn_red = ConfigSelection(default="delete", choices=userDefinedActions)
			config.movielist.btn_green = ConfigSelection(default="move", choices=userDefinedActions)
			config.movielist.btn_yellow = ConfigSelection(default="bookmarks", choices=userDefinedActions)
			config.movielist.btn_blue = ConfigSelection(default="sortby", choices=userDefinedActions)
			config.movielist.btn_redlong = ConfigSelection(default="rename", choices=userDefinedActions)
			config.movielist.btn_greenlong = ConfigSelection(default="copy", choices=userDefinedActions)
			config.movielist.btn_yellowlong = ConfigSelection(default="tags", choices=userDefinedActions)
			config.movielist.btn_bluelong = ConfigSelection(default="sortdefault", choices=userDefinedActions)
			config.movielist.btn_radio = ConfigSelection(default="tags", choices=userDefinedActions)
			config.movielist.btn_tv = ConfigSelection(default="gohome", choices=userDefinedActions)
			config.movielist.btn_text = ConfigSelection(default="movieoff", choices=userDefinedActions)
			config.movielist.btn_F1 = ConfigSelection(default="movieoff_menu", choices=userDefinedActions)
			config.movielist.btn_F2 = ConfigSelection(default="preview", choices=userDefinedActions)
			config.movielist.btn_F3 = ConfigSelection(default="/media", choices=userDefinedActions)
		userDefinedButtons = {
			"red": config.movielist.btn_red,
			"green": config.movielist.btn_green,
			"yellow": config.movielist.btn_yellow,
			"blue": config.movielist.btn_blue,
			"redlong": config.movielist.btn_redlong,
			"greenlong": config.movielist.btn_greenlong,
			"yellowlong": config.movielist.btn_yellowlong,
			"bluelong": config.movielist.btn_bluelong,
			"Radio": config.movielist.btn_radio,
			"TV": config.movielist.btn_tv,
			"Text": config.movielist.btn_text,
			"F1": config.movielist.btn_F1,
			"F2": config.movielist.btn_F2,
			"F3": config.movielist.btn_F3
		}

	def getinitUserDefinedActionsDescription(self, key):
		return _(userDefinedActions.get(eval("config.movielist.%s.value" % key), _("Not Defined")))

	def _callButton(self, name):
		if name.startswith("@"):
			item = self.getCurrentSelection()
			if isSimpleFile(item):
				name = name[1:]
				for p in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
					if name == p.name:
						p.__call__(self.session, item[0])
		elif name.startswith("/"):
			self.gotFilename(name)
		else:
			try:
				a = getattr(self, "do_%s" % name)
			except Exception:
				# Undefined action
				return
			a()

	def btn_red(self):
		self._callButton(config.movielist.btn_red.value)

	def btn_green(self):
		self._callButton(config.movielist.btn_green.value)

	def btn_yellow(self):
		self._callButton(config.movielist.btn_yellow.value)

	def btn_blue(self):
		self._callButton(config.movielist.btn_blue.value)

	def btn_redlong(self):
		self._callButton(config.movielist.btn_redlong.value)

	def btn_greenlong(self):
		self._callButton(config.movielist.btn_greenlong.value)

	def btn_yellowlong(self):
		self._callButton(config.movielist.btn_yellowlong.value)

	def btn_bluelong(self):
		self._callButton(config.movielist.btn_bluelong.value)

	def btn_radio(self):
		self._callButton(config.movielist.btn_radio.value)

	def btn_tv(self):
		self._callButton(config.movielist.btn_tv.value)

	def btn_text(self):
		self._callButton(config.movielist.btn_text.value)

	def btn_F1(self):
		self._callButton(config.movielist.btn_F1.value)

	def btn_F2(self):
		self._callButton(config.movielist.btn_F2.value)

	def btn_F3(self):
		self._callButton(config.movielist.btn_F3.value)

	def keyUp(self):
		if self["list"].getCurrentIndex() < 1:
			self["list"].moveToLast()
		else:
			self["list"].moveUp()

	def keyDown(self):
		if self["list"].getCurrentIndex() == len(self["list"]) - 1:
			self["list"].moveToFirst()
		else:
			self["list"].moveDown()

	def pageUp(self):
		if self["list"].getCurrentIndex() < 1:
			self["list"].moveToLast()
		else:
			self["list"].instance.moveSelection(self["list"].instance.pageUp)

	def pageDown(self):
		if self["list"].getCurrentIndex() == len(self["list"]) - 1:
			self["list"].moveToFirst()
		else:
			self["list"].instance.moveSelection(self["list"].instance.pageDown)

	def doNothing(self):
		pass

	def moveToFirstOrFirstFile(self):
		if self.list.getCurrentIndex() <= self.list.firstFileEntry:  # selection above or on first movie
			if self.list.getCurrentIndex() < 1:
				self.list.moveToLast()
			else:
				self.list.moveToFirst()
		else:
			self.list.moveToFirstMovie()

	def moveToLastOrFirstFile(self):
		if self.list.getCurrentIndex() >= self.list.firstFileEntry or self.list.firstFileEntry == len(self.list):  # selection below or on first movie or no files
			if self.list.getCurrentIndex() == len(self.list) - 1:
				self.list.moveToFirst()
			else:
				self.list.moveToLast()
		else:
			self.list.moveToFirstMovie()

	def keyNumberGlobal(self, number):
		charstr = self.numericalTextInput.getKey(number)
		if len(charstr) == 1:
			self.list.moveToChar(charstr[0], self["chosenletter"])

	def keyAsciiCode(self):
		charstr = chr(getPrevAsciiCode())
		if len(charstr) == 1:
			self.list.moveToString(charstr[0], self["chosenletter"])

	def isItemPlayable(self, index):
		item = self.list.getItem(index)
		if item:
			path = item.getPath()
			if not item.flags & eServiceReference.mustDescent:
				ext = splitext(path)[1].lower()
				if ext in IMAGE_EXTENSIONS:
					return False
				else:
					return True
		return False

	def goToPlayingService(self):
		service = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if service:
			path = service.getPath()
			if path:
				path = split(normpath(path))[0]
				if not path.endswith("/"):
					path += "/"
				self.gotFilename(path, selItem=service)
				return True
		return False

	def playNext(self):
		if self.list.playInBackground:
			if self.list.moveTo(self.list.playInBackground):
				if self.isItemPlayable(self.list.getCurrentIndex() + 1):
					self.list.moveDown()
					self.callLater(self.preview)
			else:
				self.playGoTo = 1
				self.goToPlayingService()
		else:
			self.preview()

	def playPrev(self):
		if self.list.playInBackground:
			if self.list.moveTo(self.list.playInBackground):
				if self.isItemPlayable(self.list.getCurrentIndex() - 1):
					self.list.moveUp()
					self.callLater(self.preview)
			else:
				self.playGoTo = -1
				self.goToPlayingService()
		else:
			current = self.getCurrent()
			if current is not None:
				if self["list"].getCurrentIndex() > 0:
					path = current.getPath()
					path = abspath(pathjoin(path, pardir))
					path = abspath(pathjoin(path, pardir))
					self.gotFilename(path)

	def __onClose(self):
		config.misc.standbyCounter.removeNotifier(self.standbyCountChanged)
		try:
			NavigationInstance.instance.RecordTimer.on_state_change.remove(self.list.updateRecordings)
		except Exception as e:
			print("[MovieSelection] failed to unsubscribe:", e)
			pass

	def updateDescription(self):
		if self.settings["description"] == MovieList.SHOW_DESCRIPTION:
			self["DescriptionBorder"].show()
			self["list"].instance.resize(eSize(self.listWidth, self.listHeight - self["DescriptionBorder"].instance.size().height()))
		else:
			self["Service"].newService(None)
			self["DescriptionBorder"].hide()
			self["list"].instance.resize(eSize(self.listWidth, self.listHeight))

	def pauseService(self):
		# Called when pressing Power button (go to standby)
		self.playbackStop()
		self.session.nav.stopService()

	def unPauseService(self):
		# When returning from standby. It might have been a while, so
		# reload the list.
		self.reloadList()

	def can_move(self, item):
		if not item:
			return False
		return canMove(item)

	def can_delete(self, item):
		if not item:
			return False
		return canDelete(item) or isTrashFolder(item[0])

	def can_default(self, item):
		# returns whether item is a regular file
		return isSimpleFile(item)

	def can_sort(self, item):
		return True

	def can_preview(self, item):
		return isSimpleFile(item)

	def _updateButtonTexts(self):
		for k in ("red", "green", "yellow", "blue"):
			btn = userDefinedButtons[k]
			self["key_%s" % k].setText(userDefinedActions[btn.value])

	def updateButtons(self):
		item = self.getCurrentSelection()
		for name in ("red", "green", "yellow", "blue"):
			action = userDefinedButtons[name].value
			if action.startswith("@"):
				check = self.can_default
			elif action.startswith("/"):
				check = self.can_gohome
			else:
				try:
					check = getattr(self, "can_%s" % action)
				except:
					check = self.can_default
			gui = self["key_%s" % name]
			if check(item):
				gui.show()
			else:
				gui.hide()

	def showEventInformation(self):
		from Screens.EventView import EventViewSimple
		from ServiceReference import ServiceReference
		evt = self["list"].getCurrentEvent()
		if evt:
			self.session.open(EventViewSimple, evt, ServiceReference(self.getCurrent()))

	def saveListsize(self):
		listsize = self["list"].instance.size()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()
		self.updateDescription()

	def FilePlaying(self):
		if self.session.nav.getCurrentlyPlayingServiceReference() and ":0:/" in self.session.nav.getCurrentlyPlayingServiceReference().toString():
			self.list.playInForeground = self.session.nav.getCurrentlyPlayingServiceReference()
		else:
			self.list.playInForeground = None
		self.filePlayingTimer.stop()

	def onFirstTimeShown(self):
		self.filePlayingTimer.start(100)
		self.onShown.remove(self.onFirstTimeShown)  # Just once, not after returning etc.
		self.show()
		self.reloadList(self.selectedmovie, home=True)
		del self.selectedmovie
		if config.movielist.show_live_tv_in_movielist.value:
			self.LivePlayTimer.start(100)

	def hidewaitingtext(self):
		self.hidewaitingTimer.stop()
		self["waitingtext"].hide()

	def LivePlay(self):
		if self.session.nav.getCurrentlyPlayingServiceReference():
			if ":0:/" not in self.session.nav.getCurrentlyPlayingServiceReference().toString():
				config.movielist.curentlyplayingservice.setValue(self.session.nav.getCurrentlyPlayingServiceReference().toString())
		checkplaying = self.session.nav.getCurrentlyPlayingServiceReference()
		if checkplaying:
			checkplaying = checkplaying.toString()
		if checkplaying is None or (config.movielist.curentlyplayingservice.value != checkplaying and ":0:/" not in self.session.nav.getCurrentlyPlayingServiceReference().toString()):
			self.session.nav.playService(eServiceReference(config.movielist.curentlyplayingservice.value))
		self.LivePlayTimer.stop()

	def getCurrent(self):
		# Returns selected serviceref (may be None)
		return self["list"].getCurrent()

	def getCurrentSelection(self):
		# Returns None or (serviceref, info, begin, len)
		return self["list"].l.getCurrentSelection()

	def playAsBLURAY(self, path):
		try:
			from Plugins.Extensions.BlurayPlayer import BlurayUi
			self.session.open(BlurayUi.BlurayMain, path)
			return True
		except Exception as e:
			print("[MovieSelection] Cannot open BlurayPlayer:", e)

	def playAsDVD(self, path):
		try:
			from Screens import DVD
			if path.endswith("VIDEO_TS/"):
				# strip away VIDEO_TS/ part
				path = split(path.rstrip("/"))[0]
			self.session.open(DVD.DVDPlayer, dvd_filelist=[path])
			return True
		except Exception as e:
			print("[MovieSelection] DVD Player not installed:", e)

	def playSuburi(self, path):
		suburi = splitext(path)[0][:-7]
		for ext in AUDIO_EXTENSIONS:
			if exists("%s%s" % (suburi, ext)):
				current = eServiceReference(4097, 0, "file://%s&suburi=file://%s%s" % (path, suburi, ext))
				self.close(current)
				return True

	def __serviceStarted(self):
		if not self.list.playInBackground or not self.list.playInForeground:
			return
		ref = self.session.nav.getCurrentService()
		cue = ref.cueSheet()
		if not cue:
			return
		# disable writing the stop position
		cue.setCutListEnable(2)
		# find "resume" position
		cuts = cue.getCutList()
		if not cuts:
			return
		for (pts, what) in cuts:
			if what == 3:
				last = pts
				break
		else:
			# no resume, jump to start of program (first marker)
			last = cuts[0][0]
		self.doSeekTo = last
		self.callLater(self.doSeek)

	def doSeek(self, pts=None):
		if pts is None:
			pts = self.doSeekTo
		seekable = self.getSeek()
		if seekable is None:
			return
		seekable.seekTo(pts)

	def getSeek(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		seek = service.seek()
		if seek is None or not seek.isCurrentlySeekable():
			return None
		return seek

	def callLater(self, function):
		self.previewTimer = eTimer()
		self.previewTimer.callback.append(function)
		self.previewTimer.start(10, True)

	def __evEOF(self):
		playInBackground = self.list.playInBackground
		playInForeground = self.list.playInForeground
		if not playInBackground:
			print("[MovieSelection] Not playing anything in background")
			return
		self.session.nav.stopService()
		self.list.playInBackground = None
		self.list.playInForeground = None
		if config.movielist.play_audio_internal.value:
			index = self.list.findService(playInBackground)
			if index is None:
				return  # Not found?
			next = self.list.getItem(index + 1)
			if not next:
				return
			path = next.getPath()
			ext = splitext(path)[1].lower()
			print("[MovieSelection] Next up:", path)
			if ext in AUDIO_EXTENSIONS:
				self.nextInBackground = next
				self.callLater(self.preview)
				self["list"].moveToIndex(index + 1)

		if config.movielist.show_live_tv_in_movielist.value:
			self.LivePlayTimer.start(100)

	def preview(self):
		current = self.getCurrent()
		if current is not None:
			path = current.getPath()
			if current.flags & eServiceReference.mustDescent:
				self.gotFilename(path)
			else:
				Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(self.previewCheckTimeshiftCallback)

	def startPreview(self):
		if self.nextInBackground is not None:
			current = self.nextInBackground
			self.nextInBackground = None
		else:
			current = self.getCurrent()
		playInBackground = self.list.playInBackground
		if playInBackground:
			self.list.playInBackground = None
			self.session.nav.stopService()
			if playInBackground != current:
				# come back to play the new one
				self.callLater(self.preview)
		else:
			self.list.playInBackground = current
			self.session.nav.playService(current)

	def previewCheckTimeshiftCallback(self, answer):
		if answer:
			self.startPreview()

	def seekRelative(self, direction, amount):
		if self.list.playInBackground or self.list.playInBackground:
			seekable = self.getSeek()
			if seekable is None:
				return
			seekable.seekRelative(direction, amount)

	def playbackStop(self):
		if self.list.playInBackground:
			self.list.playInBackground = None
			self.session.nav.stopService()

	def itemSelected(self, answer=True):
		current = self.getCurrent()
		if current is not None:
			path = current.getPath()
			if current.flags & eServiceReference.mustDescent:
				if BlurayPlayer is not None and isdir(pathjoin(path, "BDMV/STREAM/")):
					# force a BLU-RAY extention
					Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, "bluray", path))
					return
				if isdir(pathjoin(path, "VIDEO_TS/")) or isfile(pathjoin(path, "VIDEO_TS.IFO")):
					# force a DVD extention
					Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, ".img", path))
					return
				self.gotFilename(path)
			else:
				ext = splitext(path)[1].lower()
				if config.movielist.play_audio_internal.value and (ext in AUDIO_EXTENSIONS):
					self.preview()
					return
				if self.list.playInBackground:
					# Stop preview, come back later
					self.session.nav.stopService()
					self.list.playInBackground = None
					self.callLater(self.itemSelected)
					return
				if ext in IMAGE_EXTENSIONS:
					try:
						from Plugins.Extensions.PicturePlayer import ui
						# Build the list for the PicturePlayer UI
						filelist = []
						index = 0
						for item in self.list.list:
							p = item[0].getPath()
							if p == path:
								index = len(filelist)
							if splitext(p)[1].lower() in IMAGE_EXTENSIONS:
								filelist.append(((p, False), None))
						self.session.open(ui.Pic_Full_View, filelist, index, path)
					except Exception as ex:
						print("[MovieSelection] Cannot display", str(ex))
					return
				Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, ext, path))

	def itemSelectedCheckTimeshiftCallback(self, ext, path, answer):
		if answer:
			if ext in (".iso", ".img", ".nrg") and BlurayPlayer is not None:
				try:
					from Plugins.Extensions.BlurayPlayer import blurayinfo
					if blurayinfo.isBluray(path) == 1:
						ext = "bluray"
				except Exception as e:
					print("[MovieSelection] Error in blurayinfo:", e)
			if ext == "bluray":
				if self.playAsBLURAY(path):
					return
			elif ext in DVD_EXTENSIONS:
				if self.playAsDVD(path):
					return
			elif "_suburi." in path:
				if self.playSuburi(path):
					return
			self.movieSelected()

	# Note: DVDBurn overrides this method, hence the itemSelected indirection.
	def movieSelected(self):
		current = self.getCurrent()
		if current is not None:
			self.saveconfig()
			self.close(current)

	def doContext(self):
		current = self.getCurrent()
		if current is not None:
			self.session.openWithCallback(self.doneContext, MovieContextMenu, self, current)

	def doneContext(self, action):
		if action is not None:
			action()

	def saveLocalSettings(self):
		if not config.movielist.settings_per_directory.value:
			return
		path = pathjoin(config.movielist.last_videodir.value, ".e2settings.pkl")
		try:
			file = open(path, "wb")
			dump(self.settings, file)
			file.close()
		except Exception as e:
			print("[MovieSelection] Failed to save settings to %s: %s" % (path, e))
		# Also set config items, in case the user has a read-only disk
		config.movielist.moviesort.value = self.settings["moviesort"]
		config.movielist.description.value = self.settings["description"]
		config.usage.on_movie_eof.value = self.settings["movieoff"]
		# save movieeof values for using by hotkeys
		config.usage.on_movie_eof.save()

	def loadLocalSettings(self):
		'Load settings, called when entering a directory'
		if config.movielist.settings_per_directory.value:
			path = pathjoin(config.movielist.last_videodir.value, ".e2settings.pkl")
			try:
				file = open(path, "rb")
				updates = load(file)
				file.close()
				self.applyConfigSettings(updates)
			except (IOError, OSError) as e:
				updates = {
					"moviesort": config.movielist.moviesort.default,
					"description": config.movielist.description.default,
					"movieoff": config.usage.on_movie_eof.default
				}
				self.applyConfigSettings(updates)
				pass  # ignore fail to open errors
			except Exception as e:
				print("[MovieSelection] Failed to load settings from %s: %s" % (path, e))
		else:
			updates = {
				"moviesort": config.movielist.moviesort.value,
				"description": config.movielist.description.value,
				"movieoff": config.usage.on_movie_eof.value
				}
			self.applyConfigSettings(updates)

		# Remember this starting sort method for this dir.
		# selectSortby() needs this to highlight the current sort and
		# do_sort() needs it to know whence to move on.
		#
		self["list"].current_sort = self.settings["moviesort"]

	def applyConfigSettings(self, updates):
		needUpdate = ("description" in updates) and (updates["description"] != self.settings["description"])
		self.settings.update(updates)
		if needUpdate:
			self["list"].setDescriptionState(self.settings["description"])
			self.updateDescription()
		if self.settings["moviesort"] != self["list"].sort_type:
			self["list"].setSortType(int(self.settings["moviesort"]))
			needUpdate = True
		if self.settings["movieoff"] != self.movieOff:
			self.movieOff = self.settings["movieoff"]
			needUpdate = True
		config.movielist.moviesort.value = self.settings["moviesort"]
		config.movielist.description.value = self.settings["description"]
		return needUpdate

	def sortBy(self, newType):
		print("[MovieSelection] SORTBY:", newType)
		if newType < MovieList.TRASHSORT_SHOWRECORD:
			self.settings["moviesort"] = newType
			# If we are using per-directory sort methods then set it now...
			#
			if config.movielist.settings_per_directory.value:
				self.saveLocalSettings()
			else:
				# ..otherwise, if we are setting permanent sort methods, save it,
				# while, for temporary sort methods, indicate to MovieList.py to
				# use a temporary sort override.
				#
				if config.movielist.perm_sort_changes.value:
					config.movielist.moviesort.setValue(newType)
					config.movielist.moviesort.save()
				else:
					self["list"].temp_sort = newType
			self.setSortType(newType)
			# Unset specific trash-sorting if other sort chosen while in Trash
			if MovieList.InTrashFolder:
				config.usage.trashsort_deltime.value = "no"
		else:
			if newType == MovieList.TRASHSORT_SHOWRECORD:
				config.usage.trashsort_deltime.value = "show record time"
			elif newType == MovieList.TRASHSORT_SHOWDELETE:
				config.usage.trashsort_deltime.value = "show delete time"
		self.reloadList()

	def showDescription(self, newType):
		self.settings["description"] = newType
		self.saveLocalSettings()
		self.setDescriptionState(newType)
		self.updateDescription()

	def abort(self):
		global playlist
		del playlist[:]
		if self.list.playInBackground:
			self.list.playInBackground = None
			self.session.nav.stopService()
			self.callLater(self.abort)
			return
		self.saveconfig()
		self.close(None)

	def saveconfig(self):
		config.movielist.last_selected_tags.value = self.selected_tags if self.selected_tags else []

	def configure(self):
		self.session.openWithCallback(self.configureDone, MovieSelectionSetup)

	def configureDone(self, result):
		if result is True:
			self.applyConfigSettings({
				"moviesort": config.movielist.moviesort.value,
				"description": config.movielist.description.value,
				"movieoff": config.usage.on_movie_eof.value
			})
			self.saveLocalSettings()
			self._updateButtonTexts()
			self["list"].setItemsPerPage()
			self["list"].setFontsize()
			self.reloadList()
			self.updateDescription()

	def can_sortby(self, item):
		return True

	def do_sortby(self):
		self.selectSortby()

	# This is the code that displays a menu of all sort options and lets you
	# select one to use.  The "Sort by" option.
	# It must be compatible with do_sort().
	# NOTE: sort methods may be temporary or permanent!
	#
	def selectSortby(self):
		menu = []
		index = 0
		used = 0
		# Determine the current sorting method so that it may be highlighted...
		#
		for x in l_moviesort:
			if int(x[0]) == self["list"].current_sort:
				used = index
			menu.append((_(x[1]), x[0], "%d" % index))
			index += 1
		if MovieList.InTrashFolder:
			for x in l_trashsort:
				if x[3] == config.usage.trashsort_deltime.value:
					used = index
				menu.append((_(x[1]), x[0], "%d" % index))
				index += 1

		# Add a help window message to remind the user whether this will set a
		# per-directory method or just a temporary override.
		# Done by using the way that ChoiceBox handles a multi-line title:
		# it makes line1 the title and all succeeding lines go into the "text"
		# display.
		# We set a text for "settings_per_directory" even though it will never
		# get here...just in case one day it does.
		#
		title = _("Sort list:")
		if config.movielist.settings_per_directory.value:
			title = "%s\n\n%s" % (title, _("Set the sort method for this directory"))
		else:
			if config.movielist.perm_sort_changes.value:
				title = "%s\n\n%s" % (title, _("Set the global sort method"))
			else:
				title = "%s\n\n%s" % (title, _("Set a temporary sort method for this directory"))
				# You can't be currently using a temporary sort method if you use
				# perm_sort_changes
				if self["list"].current_sort != self["list"].sort_type:
					title = "%s\n%s" % (title, _("(You are currently using a temporary sort method)"))
		self.session.openWithCallback(self.sortbyMenuCallback, ChoiceBox, title=title, list=menu, selection=used)

	def getPixmapSortIndex(self, which):
		index = int(which)
		if index == MovieList.SORT_ALPHA_DATE_OLDEST_FIRST:
			index = MovieList.SORT_ALPHANUMERIC
		elif index == MovieList.SORT_ALPHAREV_DATE_NEWEST_FIRST:
			index = MovieList.SORT_ALPHANUMERIC_REVERSE
		elif (index == MovieList.TRASHSORT_SHOWRECORD) or (index == MovieList.TRASHSORT_SHOWDELETE):
			index = MovieList.SORT_RECORDED
		return index - 1

	def sortbyMenuCallback(self, choice):
		if choice is None:
			return
		self.sortBy(int(choice[1]))
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(choice[1]))

	def getTagDescription(self, tag):
		# TODO: access the tag database
		return tag

	def updateTags(self):
		# get a list of tags available in this list
		self.tags = self["list"].tags

	def setDescriptionState(self, val):
		self["list"].setDescriptionState(val)

	def setSortType(self, type):
		self["list"].setSortType(type)

	def setCurrentRef(self, path):
		self.current_ref = eServiceReference("2:0:1:0:0:0:0:0:0:0:" + path.replace(':', '%3a'))
		# Magic: this sets extra things to show
		if config.movielist.hide_images.value:
			self.current_ref.setName("16384:jpg 16384:jpeg 16384:png 16384:gif 16384:bmp 16384:svg")
		else:
			self.current_ref.setName("16384:png")

	def reloadList(self, sel=None, home=False):
		self.reload_sel = sel
		self.reload_home = home
		self["waitingtext"].visible = True
		self.pathselectEnabled = False
		self.callLater(self.reloadWithDelay)

	def reloadWithDelay(self):
		if not isdir(config.movielist.last_videodir.value):
			path = defaultMoviePath()
			config.movielist.last_videodir.value = path
			config.movielist.last_videodir.save()
			self.setCurrentRef(path)
			self["freeDiskSpace"].path = path
			self["TrashcanSize"].update(path)
		else:
			self["TrashcanSize"].update(config.movielist.last_videodir.value)
		if self.reload_sel is None:
			self.reload_sel = self.getCurrent()
		if config.usage.movielist_trashcan.value and access(config.movielist.last_videodir.value, W_OK):
			trash = createTrashFolder(config.movielist.last_videodir.value)
		self.loadLocalSettings()
		self["list"].reload(self.current_ref, self.selected_tags)
		self.updateTags()
		title = ""
		if config.usage.setup_level.index >= 2:  # expert+
			title += config.movielist.last_videodir.value
		if self.selected_tags:
			title += " - %s" % ",".join(self.selected_tags)
		self.setTitle(title)
		self.displayMovieOffStatus()
		self.displaySortStatus()
		if not (self.reload_sel and self["list"].moveTo(self.reload_sel)):
			if self.reload_home:
				self["list"].moveToFirstMovie()
		self["freeDiskSpace"].update()
		self["waitingtext"].visible = False
		self.createPlaylist()
		if self.playGoTo:
			if self.isItemPlayable(self.list.getCurrentIndex() + 1):
				if self.playGoTo > 0:
					self.list.moveDown()
				else:
					self.list.moveUp()
				self.playGoTo = None
				self.callLater(self.preview)
		self.callLater(self.enablePathSelect)

	def enablePathSelect(self):
		self.pathselectEnabled = True

	def doPathSelect(self):
		if self.pathselectEnabled:
			self.session.openWithCallback(
				self.gotFilename,
				MovieLocationBox,
				_("Please select the movie path..."),
				config.movielist.last_videodir.value
			)

	def gotFilename(self, res, selItem=None):
		def servicePinEntered(res, selItem, result):
			if result:
				from Components.ParentalControl import parentalControl
				parentalControl.setSessionPinCached()
				parentalControl.hideBlacklist()
				self.gotFilename(res, selItem)
			elif result == False:
				self.session.open(MessageBox, _("The PIN code you entered is wrong."), MessageBox.TYPE_INFO, timeout=5)
		if not res:
			return
		# serviceref must end with /
		if not res.endswith("/"):
			res += "/"
		currentDir = config.movielist.last_videodir.value
		if res != currentDir:
			if isdir(res):
				baseName = basename(res[:-1])
				if config.ParentalControl.servicepinactive.value and baseName.startswith(".") and not baseName.startswith(".Trash"):
					from Components.ParentalControl import parentalControl
					if not parentalControl.sessionPinCached:
						self.session.openWithCallback(boundFunction(servicePinEntered, res, selItem), PinInput, pinList=[x.value for x in config.ParentalControl.servicepin], triesEntry=config.ParentalControl.retries.servicepin, title=_("Please enter the correct PIN code"), windowTitle=_("Enter PIN code"))
						return
				config.movielist.last_videodir.value = res
				config.movielist.last_videodir.save()
				self.loadLocalSettings()
				self.setCurrentRef(res)
				self["freeDiskSpace"].path = res
				self["TrashcanSize"].update(res)
				if selItem:
					self.reloadList(home=True, sel=selItem)
				else:
					self.reloadList(home=True, sel=eServiceReference("2:0:1:0:0:0:0:0:0:0:" + currentDir.replace(':', '%3a')))
			else:
				mbox = self.session.open(
					MessageBox,
					_("Directory %s does not exist.") % res,
					type=MessageBox.TYPE_ERROR,
					timeout=5
					)
				mbox.setTitle(self.getTitle())

	def pinEntered(self, answer):
		if answer:
			from Components.ParentalControl import parentalControl
			parentalControl.setSessionPinCached()
			parentalControl.hideBlacklist()
			self.reloadList()
		elif answer is not None:
			self.session.openWithCallback(self.close, MessageBox, _("The PIN code you entered is wrong."), MessageBox.TYPE_ERROR)

	def showAll(self):
		self.selected_tags_ele = None
		self.selected_tags = None
		self.saveconfig()
		self.reloadList(home=True)

	def showTagsN(self, tagele):
		if not self.tags:
			self.showTagWarning()
		elif not tagele or (self.selected_tags and tagele.value in self.selected_tags) or not tagele.value in self.tags:
			self.showTagsMenu(tagele)
		else:
			self.selected_tags_ele = tagele
			self.selected_tags = self.tags[tagele.value]
			self.reloadList(home=True)

	def showTagsFirst(self):
		self.showTagsN(config.movielist.first_tags)

	def showTagsSecond(self):
		self.showTagsN(config.movielist.second_tags)

	def can_tags(self, item):
		return self.tags

	def do_tags(self):
		self.showTagsN(None)

	def tagChosen(self, tag):
		if tag is not None:
			if tag[1] is None:  # all
				self.showAll()
				return
			# TODO: Some error checking maybe, don't wanna crash on KeyError
			self.selected_tags = self.tags[tag[0]]
			if self.selected_tags_ele:
				self.selected_tags_ele.value = tag[0]
				self.selected_tags_ele.save()
			self.saveconfig()
			self.reloadList(home=True)

	def showTagsMenu(self, tagele):
		self.selected_tags_ele = tagele
		lst = [(_("show all tags"), None)] + [(tag, self.getTagDescription(tag)) for tag in sorted(self.tags)]
		self.session.openWithCallback(self.tagChosen, ChoiceBox, title=_("Please select the tag to filter..."), list=lst, skin_name="MovieListTags")

	def showTagWarning(self):
		mbox = self.session.open(MessageBox, _("No tags are set on these movies."), MessageBox.TYPE_ERROR)
		mbox.setTitle(self.getTitle())

	def selectMovieLocation(self, title, callback):
		bookmarks = [("(%s...)" % _("Other"), None)]
		buildMovieLocationList(bookmarks)
		self.onMovieSelected = callback
		self.movieSelectTitle = title
		self.session.openWithCallback(self.gotMovieLocation, ChoiceBox, title=title, list=bookmarks)

	def gotMovieLocation(self, choice):
		if not choice:
			# cancelled
			self.onMovieSelected(None)
			del self.onMovieSelected
			return
		if isinstance(choice, tuple):
			if choice[1] is None:
				# Display full browser, which returns string
				self.session.openWithCallback(
					self.gotMovieLocation,
					MovieLocationBox,
					self.movieSelectTitle,
					config.movielist.last_videodir.value
				)
				return
			choice = choice[1]
		choice = normpath(choice)
		self.rememberMovieLocation(choice)
		self.onMovieSelected(choice)
		del self.onMovieSelected

	def rememberMovieLocation(self, where):
		if where in last_selected_dest:
			last_selected_dest.remove(where)
		last_selected_dest.insert(0, where)
		if len(last_selected_dest) > 5:
			del last_selected_dest[-1]

	def playBlurayFile(self):
		if self.playfile:
			Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(self.autoBlurayCheckTimeshiftCallback)

	def autoBlurayCheckTimeshiftCallback(self, answer):
		if answer:
			playRef = eServiceReference(3, 0, self.playfile)
			self.playfile = ""
			self.close(playRef)

	def isBlurayFolderAndFile(self, service):
		self.playfile = ""
		folder = pathjoin(service.getPath(), "STREAM/")
		if "BDMV/STREAM/" not in folder:
			folder = "%s%s" % (folder[:-7], "BDMV/STREAM/")
		if isdir(folder):
			fileSize = 0
			for name in listdir(folder):
				filename = pathjoin(folder, name)
				try:
					if name.endswith(".m2ts"):
						size = stat(filename).st_size
						if size > fileSize:
							fileSize = size
							self.playfile = filename
				except (IOError, OSError) as err:
					print("[MovieSelection] Error %d: Unable to calculate size for '%s'!  (%s)" % (err.errno, filename, err.strerror))
			if self.playfile:
				return True
		return False

	def can_bookmarks(self, item):
		return True

	def do_bookmarks(self):
		self.selectMovieLocation(title=_("Please select the movie path..."), callback=self.gotFilename)

	def can_addbookmark(self, item):
		return True

	def exist_bookmark(self):
		path = config.movielist.last_videodir.value
		if path in config.movielist.videodirs.value:
			return True
		return False

	def do_addbookmark(self):
		path = config.movielist.last_videodir.value
		if path in config.movielist.videodirs.value:
			if len(path) > 40:
				path = "...%s" % path[-40:]
			mbox = self.session.openWithCallback(self.removeBookmark, MessageBox, _("Do you really want to remove your bookmark of %s?") % path)
			mbox.setTitle(self.getTitle())
		else:
			config.movielist.videodirs.value += [path]
			config.movielist.videodirs.save()

	def removeBookmark(self, yes):
		if not yes:
			return
		path = config.movielist.last_videodir.value
		bookmarks = config.movielist.videodirs.value
		bookmarks.remove(path)
		config.movielist.videodirs.value = bookmarks
		config.movielist.videodirs.save()

	def can_createdir(self, item):
		return True

	def do_createdir(self):
		dirname = ""
		item = self.getCurrentSelection()
		if item is not None and item[0] and item[1] and not isFolder(item):
			info = item[1]
			dirname = info.getName(item[0])
			full_name = split(item[0].getPath())[1]
			if full_name == dirname:  # split extensions for files without metafile
				dirname, self.extension = splitext(dirname)
		self.session.openWithCallback(self.createDirCallback, VirtualKeyBoard,
			title=_("Please enter the name of the new directory"),
			text=dirname)

	def createDirCallback(self, name):
		if not name:
			return
		msg = None
		try:
			path = pathjoin(config.movielist.last_videodir.value, name)
			mkdir(path)
			if not path.endswith("/"):
				path += "/"
			self.reloadList(sel=eServiceReference("2:0:1:0:0:0:0:0:0:0:%s" % path))
		except (IOError, OSError) as e:
			print("[MovieSelection] Error %s:" % e.errno, e)
			if e.errno == 17:
				msg = _("The path %s already exists.") % name
			else:
				msg = "%s\n%s" % (_("Error"), str(e))
		except Exception as e:
			print("[MovieSelection] Unexpected error:", e)
			msg = "%s\n%s" % (_("Error"), str(e))
		if msg:
			mbox = self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR, timeout=5)
			mbox.setTitle(self.getTitle())

	def do_tageditor(self):
		item = self.getCurrentSelection()
		if not isFolder(item):
			self.session.openWithCallback(self.tageditorCallback, TagEditor, service=item[0])

	def tageditorCallback(self, tags):
		return

	def do_rename(self):
		item = self.getCurrentSelection()
		if not canRename(item):
			return
		self.extension = ""
		if isFolder(item):
			p = split(item[0].getPath())
			if not p[1]:
				# if path ends in "/", p is blank.
				p = split(p[0])
			name = p[1]
		else:
			info = item[1]
			name = info.getName(item[0])
			full_name = split(item[0].getPath())[1]
			if full_name == name:  # split extensions for files without metafile
				name, self.extension = splitext(name)

		self.session.openWithCallback(self.renameCallback, VirtualKeyBoard,
			title=_("Rename"),
			text=name)

	def do_decode(self):
		from ServiceReference import ServiceReference
		item = self.getCurrentSelection()
		info = item[1]
		filepath = item[0].getPath()
		if not filepath.endswith(".ts"):
			return
		serviceref = ServiceReference(None, reftype=eServiceReference.idDVB, path=filepath)
		name = "%s - decoded" % info.getName(item[0])
		description = info.getInfoString(item[0], iServiceInformation.sDescription)
		begin = int(time())
		recording = RecordTimerEntry(serviceref, begin, begin + 3600, name, description, 0, dirname=preferredTimerPath())
		recording.dontSave = True
		recording.autoincrease = True
		recording.setAutoincreaseEnd()
		new_eit_name = recording.calculateFilename(name)
		self.session.nav.RecordTimer.record(recording, ignoreTSC=True)
		self.copy_eit_file("%s.eit" % filepath[:-3], "%s.eit" % new_eit_name)

	def copy_eit_file(self, original_eit, new_eit):
		if isfile(original_eit):
			from shutil import copy2
			copy2(original_eit, new_eit)

	def renameCallback(self, name):
		if not name:
			return
		name = "".join((name.strip(), self.extension))
		item = self.getCurrentSelection()
		newbasename = name.strip()
		if item and item[0]:
			try:
				path = item[0].getPath().rstrip("/")
				meta = "%s.meta" % path
				if isfile(meta):
					# if .meta file is present don't rename files. Only set new name in .meta
					name = "".join((newbasename, self.extension))
					metafile = open(meta, "r+")
					sid = metafile.readline()
					oldtitle = metafile.readline()
					rest = metafile.read()
					metafile.seek(0)
					metafile.write("%s%s\n%s" % (sid, name, rest))
					metafile.truncate()
					metafile.close()
					index = self.list.getCurrentIndex()
					info = self.list.list[index]
					if hasattr(info[3], "txt"):
						info[3].txt = name
					else:
						self.list.invalidateCurrentItem()
					return
				# rename all files
				msg = None
				path, filename = split(oldfilename)
				if item[0].flags & eServiceReference.mustDescent:  # directory
					newfilename = pathjoin(path, newbasename)
					print("[MovieSelection] rename dir", oldfilename, "to", newfilename)
					rename(oldfilename, newfilename)
				else:
					if oldfilename.endswith(self.extension):
						oldbasename = oldfilename[:-len(self.extension)]
					renamelist = []
					dont_rename = False
					for ext in (".eit", "%s.cuts" % self.extension, self.extension):
						newfilename = "%s%s" % (pathjoin(path, newbasename), ext)
						oldfilename = "%s%s" % (pathjoin(path, oldbasename), ext)
						if not isfile(oldfilename):  # .eit and .cuts maybe not present
							continue
						if not isfile(newfilename):
							renamelist.append((oldfilename, newfilename))
						else:
							msg = _("The path %s already exists.") % name
							dont_rename = True
							break
					if not dont_rename:
						for r in renamelist:
							print("[MovieSelection] rename", r[0], "to", r[1])
							rename(r[0], r[1])
				self.reloadList(sel=eServiceReference("2:0:1:0:0:0:0:0:0:0:%s" % newfilename))
			except (IOError, OSError) as e:
				print("[MovieSelection] Error %s:" % e.errno, e)
				if e.errno == 17:
					msg = _("The path %s already exists.") % name
				else:
					msg = "%s\n%s" % (_("Error"), str(e))
			except Exception as e:
				import traceback
				print("[MovieSelection] Unexpected error:", e)
				traceback.print_exc()
				msg = "%s\n%s" % (_("Error"), str(e))
			if msg:
				mbox = self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR, timeout=5)
				mbox.setTitle(self.getTitle())

	def do_reset(self):
		current = self.getCurrent()
		if current:
			resetMoviePlayState("%s.cuts" % current.getPath(), current)
			self["list"].invalidateCurrentItem()  # trigger repaint

	def do_move(self):
		item = self.getCurrentSelection()
		if canMove(item):
			current = item[0]
			info = item[1]
			if info is None:
				# Special case
				return
			name = info and info.getName(current) or _("this recording")
			path = normpath(current.getPath())
			# show a more limited list of destinations, no point
			# in showing mountpoints.
			title = "%s %s" % (_("Select destination for:"), name)
			bookmarks = [("(%s...)" % _("Other"), None)]
			inlist = []
			# Subdirs
			try:
				base = split(path)[0]
				for fn in listdir(base):
					if not fn.startswith("."):  # Skip hidden things
						d = pathjoin(base, fn)
						if isdir(d) and (d not in inlist):
							bookmarks.append((fn, d))
							inlist.append(d)
			except Exception as e:
				print("[MovieSelection]", e)
			# Last favourites
			for d in last_selected_dest:
				if d not in inlist:
					bookmarks.append((d, d))
			# Other favourites
			for d in config.movielist.videodirs.value:
				d = normpath(d)
				bookmarks.append((d, d))
				inlist.append(d)
			for p in harddiskmanager.getMountedPartitions():
				d = normpath(p.mountpoint)
				if d not in inlist:
					bookmarks.append((p.description, d))
					inlist.append(d)
			self.onMovieSelected = self.gotMoveMovieDest
			self.movieSelectTitle = title
			self.session.openWithCallback(self.gotMovieLocation, ChoiceBox, title=title, list=bookmarks)

	def gotMoveMovieDest(self, choice):
		if not choice:
			return
		dest = normpath(choice)
		try:
			item = self.getCurrentSelection()
			current = item[0]
			if item[1] is None:
				name = None
			else:
				name = item[1].getName(current)
			moveServiceFiles(current, dest, name)
			self["list"].removeService(current)
		except Exception as e:
			mbox = self.session.open(MessageBox, str(e), MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def do_copy(self):
		item = self.getCurrentSelection()
		if canCopy(item):
			current = item[0]
			info = item[1]
			if info is None:
				# Special case
				return
			name = info and info.getName(current) or _("this recording")
			self.selectMovieLocation(title="%s %s" % (_("Select copy destination for:"), name), callback=self.gotCopyMovieDest)

	def gotCopyMovieDest(self, choice):
		if not choice:
			return
		dest = normpath(choice)
		try:
			item = self.getCurrentSelection()
			current = item[0]
			if item[1] is None:
				name = None
			else:
				name = item[1].getName(current)
			copyServiceFiles(current, dest, name)
		except Exception as e:
			mbox = self.session.open(MessageBox, str(e), MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def stopTimer(self, timer):
		if timer.isRunning():
			if timer.repeated:
				timer.enable()
				timer.processRepeated(findRunningEvent=False)
				self.session.nav.RecordTimer.doActivate(timer)
			else:
				timer.afterEvent = AFTEREVENT.NONE
				NavigationInstance.instance.RecordTimer.removeEntry(timer)

	def onTimerChoice(self, choice):
		if isinstance(choice, tuple) and choice[1]:
			choice, timer = choice[1]
			if not choice:
				# cancel
				return
			if "s" in choice:
				self.stopTimer(timer)
			if "d" in choice:
				self.delete(True)

	def do_delete(self):
		self.delete()

	def delete(self, *args):
		item = self.getCurrentSelection()
		if not item or args and (not args[0]):
			# cancelled by user (passing any arg means it's a dialog return)
			return
		current = item[0]
		info = item[1]
		cur_path = realpath(current.getPath())
		if not exists(cur_path):
			# file does not exist.
			return
		st = stat(cur_path)
		name = info and info.getName(current) or _("this recording")
		are_you_sure = ""
		pathtest = info and info.getName(current)
		if not pathtest:
			return
		if item and isTrashFolder(item[0]):
			# Red button to empty trashcan...
			self.purgeAll()
			return
		if current.flags & eServiceReference.mustDescent:
			files = 0
			subdirs = 0
			if ".Trash" not in cur_path and config.usage.movielist_trashcan.value:
				if isFolder(item):
					are_you_sure = _("Do you really want to move to the trash can ?")
					subdirs += 1
				else:
					args = True
				if args:
					trash = createTrashFolder(cur_path)
					if trash:
						try:
							moveServiceFiles(current, trash, name, allowCopy=True)
							self["list"].removeService(current)
							self.showActionFeedback("%s %s" % (_("Deleted"), name))
							return
						except:
							msg = "%s\n" % _("Cannot move to the trash can")
							are_you_sure = _("Do you really want to delete %s ?") % name
					else:
						msg = "%s\n" % _("Cannot move to the trash can")
						are_you_sure = _("Do you really want to delete %s ?") % name
				for fn in listdir(cur_path):
					if (fn != ".") and (fn != ".."):
						ffn = pathjoin(cur_path, fn)
						if isdir(ffn):
							subdirs += 1
						else:
							tempfn, tempfext = splitext(fn)
							if tempfext not in (".eit", ".ap", ".cuts", ".meta", ".sc"):
								files += 1
				if files or subdirs:
					folder_filename = split(split(name)[0])[1]
					mbox = self.session.openWithCallback(self.delete, MessageBox, _("'%s' contains %d file(s) and %d sub-directories.\n") % (folder_filename, files, subdirs - 1) + are_you_sure)
					mbox.setTitle(self.getTitle())
					return
			else:
				if ".Trash" in cur_path:
					are_you_sure = _("Do you really want to permanently remove from the trash can ?")
				else:
					are_you_sure = _("Do you really want to delete ?")
				if args:
					try:
						msg = ""
						deleteFiles(cur_path, name)
						self["list"].removeService(current)
						self.showActionFeedback("%s %s" % (_("Deleted"), name))
						return
					except Exception as e:
						print("[MovieSelection] Weird error moving to trash", e)
						msg = "%s\n%s\n" % (_("Cannot delete file"), str(e))
						return
				for fn in listdir(cur_path):
					if (fn != ".") and (fn != ".."):
						ffn = pathjoin(cur_path, fn)
						if isdir(ffn):
							subdirs += 1
						else:
							tempfn, tempfext = splitext(fn)
							if tempfext not in (".eit", ".ap", ".cuts", ".meta", ".sc"):
								files += 1
				if files or subdirs:
					folder_filename = split(split(name)[0])[1]
					mbox = self.session.openWithCallback(self.delete, MessageBox, _("'%s' contains %d file(s) and %d sub-directories.\n") % (folder_filename, files, subdirs) + are_you_sure)
					mbox.setTitle(self.getTitle())
					return
				else:
					try:
						rmdir(cur_path)
					except Exception as e:
						print("[MovieSelection] Failed delete", e)
						self.session.open(MessageBox, "%s\n%s" % (_("Delete failed!"), str(e)), MessageBox.TYPE_ERROR)
					else:
						self["list"].removeService(current)
						self.showActionFeedback("%s %s" % (_("Deleted"), name))
		else:
			if not args:
				rec_filename = split(current.getPath())[1]
				if rec_filename.endswith(".ts"):
					rec_filename = rec_filename[:-3]
				if rec_filename.endswith(".stream"):
					rec_filename = rec_filename[:-7]
				for timer in NavigationInstance.instance.RecordTimer.timer_list:
					if timer.isRunning() and not timer.justplay and rec_filename in timer.Filename:
						choices = [
							(_("Cancel"), None),
							(_("Stop recording"), ("s", timer)),
							(_("Stop recording and delete"), ("sd", timer))]
						self.session.openWithCallback(self.onTimerChoice, ChoiceBox, title="%s:\n%s" % (_("Recording in progress"), name), list=choices)
						return
				if time() - st.st_mtime < 5:
					if not args:
						are_you_sure = _("Do you really want to delete ?")
						mbox = self.session.openWithCallback(self.delete, MessageBox, _("File appears to be busy.\n") + are_you_sure)
						mbox.setTitle(self.getTitle())
						return
			if ".Trash" not in cur_path and config.usage.movielist_trashcan.value:
				trash = createTrashFolder(cur_path)
				if trash:
					try:
						moveServiceFiles(current, trash, name, allowCopy=True)
						self["list"].removeService(current)
						# Files were moved to .Trash, ok.
						from Screens.InfoBarGenerics import delResumePoint
						delResumePoint(current)
						self.showActionFeedback("%s %s" % (_("Deleted"), name))
						return
					except:
						msg = "%s\n" % _("Cannot move to the trash can")
						are_you_sure = _("Do you really want to delete %s ?") % name
				else:
					msg = "%s\n" % _("Cannot move to the trash can")
					are_you_sure = _("Do you really want to delete %s ?") % name
			else:
				if ".Trash" in cur_path:
					are_you_sure = _("Do you really want to permamently remove '%s' from the trash can ?") % name
				else:
					are_you_sure = _("Do you really want to delete %s ?") % name
				msg = ""
			mbox = self.session.openWithCallback(self.deleteConfirmed, MessageBox, msg + are_you_sure)
			mbox.setTitle(self.getTitle())

	def deleteConfirmed(self, confirmed):
		if not confirmed:
			return
		item = self.getCurrentSelection()
		if item is None:
			return  # huh?
		current = item[0]
		info = item[1]
		name = info and info.getName(current) or _("this recording")
		serviceHandler = eServiceCenter.getInstance()
		offline = serviceHandler.offlineOperations(current)
		try:
			if offline is None:
				from enigma import eBackgroundFileEraser
				eBackgroundFileEraser.getInstance().erase(realpath(current.getPath()))
			else:
				if offline.deleteFromDisk(0):
					raise Exception(_("Offline delete failed"))
			self["list"].removeService(current)
			from Screens.InfoBarGenerics import delResumePoint
			delResumePoint(current)
			self.showActionFeedback("%s %s" % (_("Deleted"), name))
		except Exception as ex:
			mbox = self.session.open(MessageBox, "%s\n%s\n%s" % (_("Delete failed!"), name, str(ex)), MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def purgeAll(self):
		recordings = self.session.nav.getRecordings()
		next_rec_time = -1
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 120):
			msg = "\n%s" % _("Recording(s) are in progress or coming up in few seconds!")
		else:
			msg = ""
		mbox = self.session.openWithCallback(self.purgeConfirmed, MessageBox, _("Permanently delete all recordings in the trash can?") + msg)
		mbox.setTitle(self.getTitle())

	def purgeConfirmed(self, confirmed):
		if not confirmed:
			return
		item = self.getCurrentSelection()
		current = item[0]
		cleanAll(split(current.getPath())[0])

	def showNetworkMounts(self):
		from . import NetworkSetup
		self.session.open(NetworkSetup.NetworkMountsMenu)

	def showDeviceMounts(self):
		import Plugins.SystemPlugins.Vision.MountManager
		self.session.open(Plugins.SystemPlugins.Vision.MountManager.VISIONDevicesPanel)

	def showActionFeedback(self, text):
		if self.feedbackTimer is None:
			self.feedbackTimer = eTimer()
			self.feedbackTimer.callback.append(self.hideActionFeedback)
		else:
			self.feedbackTimer.stop()
		self.feedbackTimer.start(3000, 1)
		self.diskinfo.setText(text)

	def hideActionFeedback(self):
		self.diskinfo.update()
		current = self.getCurrent()
		if current is not None:
			self.trashinfo.update(current.getPath())

	def can_gohome(self, item):
		return True

	def do_gohome(self):
		self.gotFilename(defaultMoviePath())

	def do_sortdefault(self):
		print("[MovieSelection] SORT:", config.movielist.moviesort.value)
		config.movielist.moviesort.load()
		print("[MovieSelection] SORT:", config.movielist.moviesort.value)
		self.sortBy(int(config.movielist.moviesort.value))

	# This is the code that advances to the "next" sort method
	# on each button press.	 The "Sort" option.
	# It must be compatible with selectSortby().
	# NOTE: sort methods may be temporary or permanent!
	#
	def do_sort(self):
		index = 0
		# Find the current sort method, then advance to the next...
		#
		for index, item in enumerate(l_moviesort):
			if int(item[0]) == self["list"].current_sort:
				break
		if index >= len(l_moviesort) - 1:
			index = 0
		else:
			index += 1
		# descriptions in native languages too long...
		sorttext = l_moviesort[index][2]
		if config.movielist.btn_red.value == "sort":
			self["key_red"].setText(sorttext)
		if config.movielist.btn_green.value == "sort":
			self["key_green"].setText(sorttext)
		if config.movielist.btn_yellow.value == "sort":
			self["key_yellow"].setText(sorttext)
		if config.movielist.btn_blue.value == "sort":
			self["key_blue"].setText(sorttext)
		self.sorttimer = eTimer()
		self.sorttimer.callback.append(self._updateButtonTexts)
		self.sorttimer.start(3000, True)  # time for displaying sorting type just applied
		self.sortBy(int(l_moviesort[index][0]))
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(l_moviesort[index][0]))

	def installedMovieManagerPlugin(self):
		try:
			from Plugins.Extensions.MovieManager.ui import MovieManager
			return True
		except Exception as e:
			print("[MovieSelection] MovieManager is not installed...", e)
			return False

	def runMovieManager(self):
		if self.installedMovieManagerPlugin():
			from Plugins.Extensions.MovieManager.ui import MovieManager
			self.session.open(MovieManager, self["list"])

	def do_preview(self):
		self.preview()

	def displaySortStatus(self):
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(config.movielist.moviesort.value))
		self["movie_sort"].show()

	def can_movieoff(self, item):
		return True

	def do_movieoff(self):
		self.setNextMovieOffStatus()
		self.displayMovieOffStatus()

	def displayMovieOffStatus(self):
		self["movie_off"].setPixmapNum(config.usage.on_movie_eof.getIndex())
		self["movie_off"].show()

	def setNextMovieOffStatus(self):
		config.usage.on_movie_eof.selectNext()
		self.settings["movieoff"] = config.usage.on_movie_eof.value
		self.saveLocalSettings()

	def can_movieoff_menu(self, item):
		return True

	def do_movieoff_menu(self):
		current_movie_eof = config.usage.on_movie_eof.value
		menu = []
		for x in config.usage.on_movie_eof.choices:
			config.usage.on_movie_eof.value = x
			menu.append((config.usage.on_movie_eof.getText(), x))
		config.usage.on_movie_eof.value = current_movie_eof
		used = config.usage.on_movie_eof.getIndex()
		self.session.openWithCallback(self.movieoffMenuCallback, ChoiceBox, title=_("On end of movie"), list=menu, selection=used)

	def movieoffMenuCallback(self, choice):
		if choice is None:
			return
		self.settings["movieoff"] = choice[1]
		self.saveLocalSettings()
		self.displayMovieOffStatus()

	def createPlaylist(self):
		global playlist
		items = playlist
		del items[:]
		for index, item in enumerate(self["list"]):
			if item:
				item = item[0]
				path = item.getPath()
				if not item.flags & eServiceReference.mustDescent:
					ext = splitext(path)[1].lower()
					if ext in IMAGE_EXTENSIONS:
						continue
					else:
						items.append(item)


class MovieSelectionSummary(Screen):
	# Kludgy component to display current selection on LCD. Should use
	# parent.Service as source for everything, but that seems to have a
	# performance impact as the MovieSelection goes through hoops to prevent
	# this when the info is not selected
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["name"] = StaticText("")
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def __onShow(self):
		self.parent.list.connectSelChanged(self.selectionChanged)
		self.selectionChanged()

	def __onHide(self):
		self.parent.list.disconnectSelChanged(self.selectionChanged)

	def selectionChanged(self):
		item = self.parent.getCurrentSelection()
		if item and item[0]:
			data = item[3]
			if data and hasattr(data, "txt"):
				name = data.txt
			elif not item[1]:
				# special case, one up
				name = ".."
			else:
				name = item[1].getName(item[0])
			if item[0].flags & eServiceReference.mustDescent:
				if len(name) > 12:
					name = split(normpath(name))[1]
				name = "> %s" % name
			self["name"].text = name
		else:
			self["name"].text = ""


class MovieContextMenu(Screen, ProtectedScreen):
	# Contract: On OK returns a callable object (e.g. delete)
	def __init__(self, session, csel, service):
		self.csel = csel
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)
		self.skinName = "Setup"
		self.setTitle(_("Movie List Context Menu"))
		# No ConfigText fields in MovieBrowserConfiguration so these are not currently used.
		# self["HelpWindow"] = Pixmap()
		# self["HelpWindow"].hide()
		# self["VKeyIcon"] = Boolean(False)
		self["footnote"] = Label("")
		self["description"] = StaticText()
		# self.title = _("Movielist menu")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "MenuActions"], {
			"red": self.cancelClick,
			"ok": self.okbuttonClick,
			"cancel": self.cancelClick,
			"green": self.do_showDeviceMounts,
			"yellow": self.do_showNetworkMounts,
			"blue": self.do_selectSortby,
			"menu": self.do_configure,
			"1": self.do_addbookmark,
			"2": self.do_createdir,
			"3": self.do_delete,
			"4": self.do_move,
			"5": self.do_copy,
			"6": self.do_rename,
			"7": self.do_reset,
			"8": self.do_decode,
			"9": self.do_unhideParentalServices
		}, prio=0)
		self["key_red"] = StaticText(_("Cancel"))

		def append_to_menu(menu, args, key=""):
			menu.append(ChoiceEntryComponent(key, args))

		menu = []
		append_to_menu(menu, (_("Settings") + "...", csel.configure), key="menu")
		append_to_menu(menu, (_("Device mounts") + "...", csel.showDeviceMounts), key="green")
		append_to_menu(menu, (_("Network mounts") + "...", csel.showNetworkMounts), key="yellow")
		append_to_menu(menu, (_("Sort by") + "...", csel.selectSortby), key="blue")
		if csel.exist_bookmark():
			append_to_menu(menu, (_("Remove bookmark"), csel.do_addbookmark), key="1")
		else:
			append_to_menu(menu, (_("Add bookmark"), csel.do_addbookmark), key="1")
		append_to_menu(menu, (_("Create directory"), csel.do_createdir), key="2")
		if service:
			if (service.flags & eServiceReference.mustDescent) and isTrashFolder(service):
				append_to_menu(menu, (_("Permanently remove all deleted items"), csel.purgeAll), key="3")
			else:
				append_to_menu(menu, (_("Delete"), csel.do_delete), key="3")
				append_to_menu(menu, (_("Move"), csel.do_move), key="4")
				append_to_menu(menu, (_("Copy"), csel.do_copy), key="5")
				append_to_menu(menu, (_("Rename"), csel.do_rename), key="6")
				if not (service.flags & eServiceReference.mustDescent):
					if self.isResetable():
						append_to_menu(menu, (_("Reset playback position"), csel.do_reset), key="7")
					if service.getPath().endswith(".ts"):
						append_to_menu(menu, (_("Start offline decode"), csel.do_decode), key="8")
				elif BlurayPlayer is None and csel.isBlurayFolderAndFile(service):
					append_to_menu(menu, (_("Auto play blu-ray file"), csel.playBlurayFile))
				if config.ParentalControl.hideBlacklist.value and config.ParentalControl.storeservicepin.value != "never":
					from Components.ParentalControl import parentalControl
					if not parentalControl.sessionPinCached:
						append_to_menu(menu, (_("Unhide parental control services"), csel.unhideParentalServices), key="9")
				if isfile("%s.meta" % service.getPath().rstrip("/")):
					append_to_menu(menu, (_("Edit Tags"), csel.do_tageditor), key="bullet")
				# Plugins expect a valid selection, so only include them if we selected a non-dir
				if not (service.flags & eServiceReference.mustDescent):
					for p in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
						append_to_menu(menu, (p.description, boundFunction(p.__call__, session, service)), key="bullet")
		self["config"] = ChoiceList(menu)

	def isProtected(self):
		return self.csel.protectContextMenu and config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.context_menus.value

	def isResetable(self):
		item = self.csel.getCurrentSelection()
		return not (item[1] and moviePlayState("%s.cuts" % item[0].getPath(), item[0], item[1].getLength(item[0])) is None)

	def pinEntered(self, answer):
		if answer:
			self.csel.protectContextMenu = False
		ProtectedScreen.pinEntered(self, answer)

	def createSummary(self):
		return MovieContextMenuSummary

	def okbuttonClick(self):
		self.close(self["config"].getCurrent()[0][1])

	def do_rename(self):
		self.close(self.csel.do_rename())

	def do_copy(self):
		self.close(self.csel.do_copy())

	def do_move(self):
		self.close(self.csel.do_move())

	def do_createdir(self):
		self.close(self.csel.do_createdir())

	def do_delete(self):
		self.close(self.csel.do_delete())

	def do_unhideParentalServices(self):
		self.close(self.csel.unhideParentalServices())

	def do_configure(self):
		self.close(self.csel.configure())

	def do_showDeviceMounts(self):
		self.close(self.csel.showDeviceMounts())

	def do_showNetworkMounts(self):
		self.close(self.csel.showNetworkMounts())

	def do_addbookmark(self):
		self.close(self.csel.do_addbookmark())

	def do_selectSortby(self):
		self.close(self.csel.selectSortby())

	def do_decode(self):
		self.close(self.csel.do_decode())

	def do_reset(self):
		self.close(self.csel.do_reset())

	def cancelClick(self):
		self.close(None)


class MovieContextMenuSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["selected"] = StaticText("")
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def __onShow(self):
		self.parent["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def __onHide(self):
		self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["selected"].text = self.parent["config"].getCurrent()[0][0]


class MovieSelectionSetup(Setup):
	def __init__(self, session):
		Setup.__init__(self, session, setup="MovieSelection")
		self.setTitle(_("Movie Selection Setup"))

	def keySave(self):
		self.saveAll()
		self.close(True)

	def closeConfigList(self, closeParameters=()):
		Setup.closeConfigList(self, (False,))


playlist = []
