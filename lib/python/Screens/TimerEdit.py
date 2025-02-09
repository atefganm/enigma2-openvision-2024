# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.Label import Label
from Components.config import config
from Components.Sources.ServiceEvent import ServiceEvent
from Components.TimerList import TimerList
from Components.TimerSanityCheck import TimerSanityCheck
from Components.UsageConfig import preferredTimerPath, dropEPGNewLines, replaceEPGSeparator
from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT, createRecordTimerEntry
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.InputBox import PinInput
from ServiceReference import ServiceReference
from Screens.TimerEntry import TimerEntry, TimerLog
from Tools.BoundFunction import boundFunction
from Tools.FallbackTimer import FallbackTimerList
from time import time
from timer import TimerEntry as RealTimerEntry
from ServiceReference import ServiceReference
from enigma import eServiceReference, eEPGCache


class TimerEditList(Screen, ProtectedScreen):
	EMPTY = 0
	ENABLE = 1
	DISABLE = 2
	CLEANUP = 3
	DELETE = 4
	STOP = 5

	def __init__(self, session):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)
		list = []
		self.list = list
		self.url = None
		self["timerlist"] = TimerList(list)
		self["Service"] = ServiceEvent()

		self.key_red_choice = self.EMPTY
		self.key_yellow_choice = self.EMPTY
		self.key_blue_choice = self.EMPTY

		self["key_red"] = StaticText("")
		self["key_green"] = StaticText(_("Add"))
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["key_info"] = StaticText("")

		self["description"] = Label("")

		self["actions"] = ActionMap(["OkCancelActions", "NavigationActions", "DirectionActions", "ShortcutActions", "TimerEditActions"],
			{
				"ok": self.openEdit,
				"cancel": self.leave,
				"green": self.addCurrentTimer,
				"log": self.showLog,
				"left": self.pageUp,
				"right": self.pageDown,
				"up": self.moveUp,
				"down": self.moveDown,
				"upUp": self.doNothing,
				"downUp": self.doNothing,
				"leftUp": self.pageUp,
				"rightUp": self.pageDown
			}, -1)
		self.setTitle(_("Timer overview"))

		self.session.nav.RecordTimer.on_state_change.append(self.onStateChange)
		self.onShown.append(self.updateState)
		self.fallbackTimer = FallbackTimerList(self, self.fillTimerList)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.timer_menu.value and config.ParentalControl.servicepin[0].value

	def moveUp(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveUp)
		self.updateState()

	def moveDown(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveDown)
		self.updateState()

	def pageUp(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageUp)
		self.updateState()

	def pageDown(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageDown)
		self.updateState()

	def doNothing(self):
		pass

	def toggleDisabledState(self):
		cur = self["timerlist"].getCurrent()
		timer_changed = True
		if cur:
			t = cur
			if t.external:
				self.fallbackTimer.toggleTimer(t, self.refill)
			else:
				stateRunning = t.state in (1, 2)
				if t.disabled and t.repeated and stateRunning and not t.justplay:
					return
				if t.disabled:
					print("[TimerEdit] try to ENABLE timer")
					t.enable()
					timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, cur)
					if not timersanitycheck.check():
						t.disable()
						print("[TimerEdit] sanity check failed")
						simulTimerList = timersanitycheck.getSimulTimerList()
						if simulTimerList is not None:
							self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, simulTimerList)
							timer_changed = False
					else:
						print("[TimerEdit] sanity check passed")
						if timersanitycheck.doubleCheck():
							t.disable()
				else:
					if stateRunning:
						if t.isRunning() and t.repeated:
							list = (
								(_("Stop current event but not coming events"), "stoponlycurrent"),
								(_("Stop current event and disable coming events"), "stopall"),
								(_("Don't stop current event but disable coming events"), "stoponlycoming")
							)
							self.session.openWithCallback(boundFunction(self.runningEventCallback, t), ChoiceBox, title=_("A repeating event is currently recording. What would you like to do?"), list=list)
							timer_changed = False
					else:
						t.disable()
				if timer_changed:
					self.session.nav.RecordTimer.timeChanged(t)
			self.refill()

	def runningEventCallback(self, t, result):
		if result is not None and t.isRunning():
			findNextRunningEvent = True
			if result[1] == "stoponlycurrent" or result[1] == "stopall":
				findNextRunningEvent = False
				t.enable()
				t.processRepeated(findRunningEvent=False)
				self.session.nav.RecordTimer.doActivate(t)
			if result[1] == "stoponlycoming" or result[1] == "stopall":
				findNextRunningEvent = True
				t.disable()
			self.session.nav.RecordTimer.timeChanged(t)
			t.findRunningEvent = findNextRunningEvent
			self.refill()

	def removeAction(self, descr):
		actions = self["actions"].actions
		if descr in actions:
			del actions[descr]

	def updateState(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self["Service"].newService(cur.service_ref.ref)
			if cur.external:
				self["key_info"].setText("")
			else:
				self["key_info"].setText(_("Info"))
			text = dropEPGNewLines(cur.description)
			event = eEPGCache.getInstance().lookupEventId(cur.service_ref.ref, cur.eit) or 0 if cur.eit else None
			if event:
				ext_description = dropEPGNewLines(event.getExtendedDescription())
				short_description = dropEPGNewLines(event.getShortDescription())
				if text != short_description:
					if text and short_description:
						text = _("Timer:") + " " + text + "\n\n" + _("EPG:") + " " + short_description
					elif short_description:
						text = short_description
						cur.description = short_description
				if ext_description and ext_description != text:
					if text:
						text += replaceEPGSeparator(config.epg.fulldescription_separator.value) + ext_description
					else:
						text = ext_description
			if not cur.conflict_detection:
				text = _("\nConflict detection disabled!") + "\n\n" + text
			self["description"].setText(text)
			stateRunning = cur.state in (1, 2)
			if cur.state == 2 and self.key_red_choice != self.STOP:
				self["actions"].actions.update({"red": self.stopTimerQuestion})
				self["key_red"].setText(_("Stop"))
				self.key_red_choice = self.STOP
			elif cur.state != 2 and self.key_red_choice != self.DELETE:
				self["actions"].actions.update({"red": self.removeTimerQuestion})
				self["key_red"].setText(_("Delete"))
				self.key_red_choice = self.DELETE

			if cur.disabled and (self.key_yellow_choice != self.ENABLE):
				if stateRunning and cur.repeated and not cur.justplay:
					self.removeAction("yellow")
					self["key_yellow"].setText("")
					self.key_yellow_choice = self.EMPTY
				else:
					self["actions"].actions.update({"yellow": self.toggleDisabledState})
					self["key_yellow"].setText(_("Enable"))
					self.key_yellow_choice = self.ENABLE
			elif stateRunning and (not cur.repeated or cur.state == 1) and (self.key_yellow_choice != self.EMPTY):
				self.removeAction("yellow")
				self["key_yellow"].setText("")
				self.key_yellow_choice = self.EMPTY
			elif (not stateRunning or cur.repeated and cur.isRunning()) and not cur.disabled and (self.key_yellow_choice != self.DISABLE):
				self["actions"].actions.update({"yellow": self.toggleDisabledState})
				self["key_yellow"].setText(_("Disable"))
				self.key_yellow_choice = self.DISABLE
		else:
			self["description"].setText("")
			if self.key_red_choice != self.EMPTY:
				self.removeAction("red")
				self["key_red"].setText("")
				self.key_red_choice = self.EMPTY
			if self.key_yellow_choice != self.EMPTY:
				self.removeAction("yellow")
				self["key_yellow"].setText("")
				self.key_yellow_choice = self.EMPTY

		showCleanup = True
		for x in self.list:
			if (not x[0].disabled) and (x[1] == True):
				break
		else:
			showCleanup = False

		if showCleanup and (self.key_blue_choice != self.CLEANUP):
			self["actions"].actions.update({"blue": self.cleanupQuestion})
			self["key_blue"].setText(_("Cleanup"))
			self.key_blue_choice = self.CLEANUP
		elif (not showCleanup) and (self.key_blue_choice != self.EMPTY):
			self.removeAction("blue")
			self["key_blue"].setText("")
			self.key_blue_choice = self.EMPTY

	def fillTimerList(self):
		from functools import cmp_to_key

		def eol_compare(x, y):
			if x[0].state != y[0].state and x[0].state == RealTimerEntry.StateEnded or y[0].state == RealTimerEntry.StateEnded:
				return (x[0].state > y[0].state) - (x[0].state < y[0].state)
			return (x[0].begin > y[0].begin) - (x[0].begin < y[0].begin)

		self.list = []
		if self.fallbackTimer.list:
			self.list.extend([(timer, False) for timer in self.fallbackTimer.list if timer.state != 3])
			self.list.extend([(timer, True) for timer in self.fallbackTimer.list if timer.state == 3])
		self.list.extend([(timer, False) for timer in self.session.nav.RecordTimer.timer_list])
		self.list.extend([(timer, True) for timer in self.session.nav.RecordTimer.processed_timers])

		if config.usage.timerlist_finished_timer_position.index: #end of list
			self.list.sort(key=cmp_to_key(eol_compare))
		else:
			self.list.sort(key=lambda x: x[0].begin)
		self["timerlist"].l.setList(self.list)
		self.updateState()

	def showLog(self):
		cur = self["timerlist"].getCurrent()
		if cur and not cur.external:
			self.session.openWithCallback(self.finishedEdit, TimerLog, cur)
		else:
			return 0

	def openEdit(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.finishedEdit, TimerEntry, cur)

	def cleanupQuestion(self):
		self.session.openWithCallback(self.cleanupTimer, MessageBox, _("Really delete done timers?"))

	def cleanupTimer(self, delete):
		if delete:
			self.session.nav.RecordTimer.cleanup()
			self.fallbackTimer.cleanupTimers(self.refill)

	def stopTimerQuestion(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to stop current event and delete timer %s?") % (cur.name))

	def removeTimerQuestion(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to delete %s?") % (cur.name))

	def removeTimer(self, result=True):
		if result:
			cur = self["timerlist"].getCurrent()
			if cur:
				if cur.external:
					self.fallbackTimer.removeTimer(cur, self.refill)
				else:
					cur.afterEvent = AFTEREVENT.NONE
					self.session.nav.RecordTimer.removeEntry(cur)
					self.refill()

	def refill(self):
		oldsize = len(self.list)
		self.fillTimerList()
		lst = self["timerlist"]
		newsize = len(self.list)
		if oldsize and oldsize != newsize:
			idx = lst.getCurrentIndex()
			lst.entryRemoved(idx)
		else:
			lst.invalidate()
		self.updateState()

	def addCurrentTimer(self):
		event = None
		service = self.session.nav.getCurrentService()
		if service is not None:
			info = service.info()
			if info is not None:
				event = info.getEvent(0)

		# FIXME only works if already playing a service
		serviceref = ServiceReference(self.session.nav.getCurrentlyPlayingServiceOrGroup())

		if event is None:
			data = (int(time()), int(time() + 60), "", "", None)
		else:
			data = parseEvent(event, description=False)
		timer = RecordTimerEntry(serviceref, checkOldTimers=True, dirname=preferredTimerPath(), *data)
		timer.justplay = config.recording.timer_default_type.value == "zap"
		timer.always_zap = config.recording.timer_default_type.value == "zap+record"
		self.addTimer(timer)

	def addTimer(self, timer):
		self.session.openWithCallback(self.finishedAdd, TimerEntry, timer)

	def finishedEdit(self, answer):
		print("[TimerEdit] finished edit")
		if answer[0]:
			entry = answer[1]
			if entry.external_prev != entry.external:
				def removeEditTimer():
					entry.service_ref, entry.begin, entry.end, entry.external = entry.service_ref_prev, entry.begin_prev, entry.end_prev, entry.external_prev
					self.removeTimer()

				def moveEditTimerError():
					entry.external = entry.external_prev
					self.refill()
				if entry.external:
					self.fallbackTimer.addTimer(entry, removeEditTimer, moveEditTimerError)
				else:
					newentry = createRecordTimerEntry(entry)
					entry.service_ref, entry.begin, entry.end = entry.service_ref_prev, entry.begin_prev, entry.end_prev
					self.fallbackTimer.removeTimer(entry, boundFunction(self.finishedAdd, (True, newentry)), moveEditTimerError)
			elif entry.external:
				self.fallbackTimer.editTimer(entry, self.refill)
			else:
				timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, entry)
				success = False
				if not timersanitycheck.check():
					simulTimerList = timersanitycheck.getSimulTimerList()
					if simulTimerList is not None:
						for x in simulTimerList:
							if x.setAutoincreaseEnd(entry):
								self.session.nav.RecordTimer.timeChanged(x)
						if not timersanitycheck.check():
							simulTimerList = timersanitycheck.getSimulTimerList()
							if simulTimerList is not None:
								self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, timersanitycheck.getSimulTimerList())
						else:
							success = True
				else:
					success = True
				if success:
					print("[TimerEdit] sanity check passed")
					self.session.nav.RecordTimer.timeChanged(entry)
				self.fillTimerList()

	def finishedAdd(self, answer):
		print("[TimerEdit] finished add")
		if answer[0]:
			entry = answer[1]
			if entry.external:
				self.fallbackTimer.addTimer(entry, self.refill)
			else:
				simulTimerList = self.session.nav.RecordTimer.record(entry)
				if simulTimerList is not None:
					for x in simulTimerList:
						if x.setAutoincreaseEnd(entry):
							self.session.nav.RecordTimer.timeChanged(x)
					simulTimerList = self.session.nav.RecordTimer.record(entry)
					if simulTimerList is not None:
						self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList)
			self.fillTimerList()

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def leave(self):
		self.session.nav.RecordTimer.on_state_change.remove(self.onStateChange)
		self.close()

	def onStateChange(self, entry):
		self.refill()


class TimerSanityConflict(Screen):
	def __init__(self, session, timer):
		Screen.__init__(self, session)
		self.skinName = "TimerEditList"
		self.timer = timer
		self.list = []
		count = 0
		for x in timer:
			self.list.append((timer[count], False))
			count += 1
		warning_color = "\c00ffff00" # yellow
		title_text = count == 1 and warning_color + _("Channel not in services list") or warning_color + _("Timer sanity error")
		self.setTitle(title_text)

		self["timerlist"] = TimerList(self.list)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")

		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions", "MenuActions"],
			{
				"cancel": self.leave_cancel,
				"red": self.leave_cancel,
				"green": self.editTimer,
				"ok": self.editTimer,
				"yellow": self.toggleTimer,
				"blue": self.ignoreConflict,
				"up": self.moveUp,
				"down": self.moveDown,
				"log": self.showLog,
				"menu": self.openExtendedSetup
			}, -1)
		self.onShown.append(self.updateState)

	def getTimerList(self, timer):
		return [(timer, False)]

	def editTimer(self):
		self.session.openWithCallback(self.editTimerCallBack, TimerEntry, self["timerlist"].getCurrent())

	def showLog(self):
		selected_timer = self["timerlist"].getCurrent()
		if selected_timer and not selected_timer.external:
			self.session.openWithCallback(self.editTimerCallBack, TimerLog, selected_timer)
		else:
			return 0

	def editTimerCallBack(self, answer=None):
		if answer and len(answer) > 1 and answer[0] == True:
			self.session.nav.RecordTimer.timeChanged(answer[1])
			if not answer[1].disabled:
				if not self.isResolvedConflict(answer[1]):
					self.session.open(MessageBox, _("Conflict not resolved!"), MessageBox.TYPE_INFO, timeout=3)
					return
			self.leave_ok()

	def toggleTimer(self):
		selected_timer = self["timerlist"].getCurrent()
		if selected_timer and self["key_yellow"].getText() != "" and not selected_timer.isRunning():
			selected_timer.disabled = not selected_timer.disabled
			if not selected_timer.disabled:
				if not self.isResolvedConflict(selected_timer):
					timer_text = _("\nTimer '%s' disabled!") % selected_timer.name
					selected_timer.disabled = True
					self.session.open(MessageBox, _("Conflict not resolved!") + timer_text, MessageBox.TYPE_INFO, timeout=3)
					return
			self.session.nav.RecordTimer.timeChanged(selected_timer)
			self.leave_ok()

	def ignoreConflict(self):
			selected_timer = self["timerlist"].getCurrent()
			if selected_timer and selected_timer.conflict_detection:
				if config.usage.show_timer_conflict_warning.value:
					list = [(_("yes"), True), (_("no"), False), (_("yes") + " " + _("and never ask this again"), "never")]
					self.session.openWithCallback(self.ignoreConflictConfirm, MessageBox, _("Warning!\nThis is an option for advanced users.\nReally disable timer conflict detection?"), list=list)
				else:
					self.ignoreConflictConfirm(True)

	def ignoreConflictConfirm(self, answer):
		selected_timer = self["timerlist"].getCurrent()
		if answer and selected_timer and selected_timer.conflict_detection:
			if answer == "never":
				config.usage.show_timer_conflict_warning.value = False
				config.usage.show_timer_conflict_warning.save()
			selected_timer.conflict_detection = False
			selected_timer.disabled = False
			self.session.nav.RecordTimer.timeChanged(selected_timer)
			self.leave_ok()

	def leave_ok(self):
		if self.isResolvedConflict():
			self.close((True, self.timer[0]))
		else:
			timer_text = ""
			selected_timer = self["timerlist"].getCurrent()
			if selected_timer and selected_timer == self.timer[0]:
				if not self.timer[0].isRunning() and not self.timer[0].disabled:
					self.timer[0].disabled = True
					self.session.nav.RecordTimer.timeChanged(self.timer[0])
					timer_text = _("\nTimer '%s' disabled!") % self.timer[0].name
			self.updateState()
			self.session.open(MessageBox, _("Conflict not resolved!") + timer_text, MessageBox.TYPE_ERROR, timeout=3)

	def leave_cancel(self):
		isTimerSave = self.timer[0] in self.session.nav.RecordTimer.timer_list
		if self.isResolvedConflict() or not isTimerSave:
			self.close((False, self.timer[0]))
		else:
			timer_text = ""
			if not self.timer[0].isRunning() and not self.timer[0].disabled:
				self.timer[0].disabled = True
				self.session.nav.RecordTimer.timeChanged(self.timer[0])
				timer_text = _("\nTimer '%s' disabled!") % self.timer[0].name
			self.session.openWithCallback(self.canceling, MessageBox, _("Conflict not resolved!") + timer_text, MessageBox.TYPE_INFO, timeout=3)

	def canceling(self, answer=None):
		self.close((False, self.timer[0]))

	def isResolvedConflict(self, checktimer=None):
		timer = checktimer or self.timer[0]
		timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, timer)
		success = False
		if not timersanitycheck.check():
			simulTimerList = timersanitycheck.getSimulTimerList()
			if simulTimerList is not None:
				for x in simulTimerList:
					if x.setAutoincreaseEnd(timer):
						self.session.nav.RecordTimer.timeChanged(x)
				if timersanitycheck.check():
					success = True
		else:
			success = True
		return success

	def openExtendedSetup(self):
		menu = []
		if not config.usage.show_timer_conflict_warning.value:
			menu.append((_("Show warning before set 'Ignore conflict'"), "blue_key_warning"))

		def showAction(choice):
			if choice is not None:
				if choice[1] == "blue_key_warning":
					config.usage.show_timer_conflict_warning.value = True
					config.usage.show_timer_conflict_warning.save()
		if menu:
			self.session.openWithCallback(showAction, ChoiceBox, title=_("Select action"), list=menu)

	def moveUp(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveUp)
		self.updateState()

	def moveDown(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveDown)
		self.updateState()

	def updateState(self):
		selected_timer = self["timerlist"].getCurrent()
		if selected_timer:
			self["key_green"].setText(_("Edit"))
			if selected_timer.disabled:
				self["key_yellow"].setText(_("Enable"))
			elif selected_timer.isRunning() and not selected_timer.repeated:
				self["key_yellow"].setText("")
			elif not selected_timer.isRunning() or selected_timer.repeated:
				self["key_yellow"].setText(_("Disable"))
			if selected_timer.conflict_detection:
				self["key_blue"].setText(_("Ignore conflict"))
			else:
				self["key_blue"].setText("")
		else:
			self["key_green"].setText("")
			self["key_yellow"].setText("")
			self["key_blue"].setText("")
