# -*- coding: utf-8 -*-
from os import listdir, rmdir
from os.path import exists, isdir, join, isfile
from bisect import insort
from Components.ActionMap import loadKeymap
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.Import import my_import
#from Tools.Profile import profile
from Plugins.Plugin import PluginDescriptor


class PluginComponent:
	firstRun = True
	restartRequired = False

	def __init__(self):
		self.plugins = {}
		self.pluginList = []
		self.installedPluginList = []
		self.setPluginPrefix("Plugins.")
		self.resetWarnings()

	def setPluginPrefix(self, prefix):
		self.prefix = prefix

	def addPlugin(self, plugin):
		if self.firstRun or not plugin.needsRestart:
			self.pluginList.append(plugin)
			for x in plugin.where:
				insort(self.plugins.setdefault(x, []), plugin)
				if x == PluginDescriptor.WHERE_AUTOSTART:
					plugin.__call__(reason=0)
		else:
			self.restartRequired = True

	def removePlugin(self, plugin):
		self.pluginList.remove(plugin)
		for x in plugin.where:
			self.plugins[x].remove(plugin)
			if x == PluginDescriptor.WHERE_AUTOSTART:
				plugin(reason=1)

	def readPluginList(self, directory):
		"""enumerates plugins"""
		new_plugins = []
		for c in listdir(directory):
			directory_category = join(directory, c)
			if not isdir(directory_category):
				continue
			for pluginname in listdir(directory_category):
				if pluginname == "__pycache__" or pluginname == "WebInterface":
					continue
				path = join(directory_category, pluginname)
				if isdir(path):
#						profile('plugin ' + pluginname)
						try:
							plugin = my_import('.'.join(["Plugins", c, pluginname, "plugin"]))
							plugins = plugin.Plugins(path=path)
						except Exception as exc:
							print("[PluginComponent] Plugin ", c + "/" + pluginname, "failed to load:", exc)
							# supress errors due to missing plugin.py* files (badly removed plugin)
							for fn in ('plugin.py', 'plugin.pyc', 'plugin.pyo'):
								if exists(join(path, fn)):
									self.warnings.append((c + "/" + pluginname, str(exc)))
									from traceback import print_exc
									print_exc()
									break
							else:
								print("[PluginComponent] Plugin probably removed, but not cleanly in", path)
								try:
									rmdir(path)
								except:
									pass
							continue

						# allow single entry not to be a list
						if not isinstance(plugins, list):
							plugins = [plugins]

						for p in plugins:
							p.path = path
							p.updateIcon(path)
							new_plugins.append(p)

						keymap = join(path, "keymap.xml")
						if isfile(keymap):
							try:
								loadKeymap(keymap)
							except Exception as exc:
								print("[PluginComponent] keymap for plugin %s/%s failed to load: " % (c, pluginname), exc)
								self.warnings.append((c + "/" + pluginname, str(exc)))

		# build a diff between the old list of plugins and the new one
		# internally, the "fnc" argument will be compared with __eq__
		plugins_added = [p for p in new_plugins if p not in self.pluginList]
		plugins_removed = [p for p in self.pluginList if not p.internal and p not in new_plugins]

		#ignore already installed but reloaded plugins
		for p in plugins_removed:
			for pa in plugins_added:
				if pa.path == p.path and pa.where == p.where:
					pa.needsRestart = False

		for p in plugins_removed:
			self.removePlugin(p)

		for p in plugins_added:
			if self.firstRun or not p.needsRestart:
				self.addPlugin(p)
			else:
				for installed_plugin in self.installedPluginList:
					if installed_plugin.path == p.path:
						if installed_plugin.where == p.where:
							p.needsRestart = False
				self.addPlugin(p)

		if self.firstRun:
			self.firstRun = False
			self.installedPluginList = self.pluginList

	def getPlugins(self, where):
		"""Get list of plugins in a specific category"""
		if not isinstance(where, list):
			# if not a list, we're done quickly, because the
			# lists are already sorted
			return self.plugins.get(where, [])
		res = []
		# Efficiently merge two sorted lists together, though this
		# appears to never be used in code anywhere...
		for x in where:
			for p in self.plugins.get(x, []):
				insort(res, p)
		return res

	def getPluginsForMenu(self, menuid):
		res = []
		for p in self.getPlugins(PluginDescriptor.WHERE_MENU):
			res += p.__call__(menuid)
		return res

	def clearPluginList(self):
		self.pluginList = []
		self.plugins = {}

	def reloadPlugins(self, dummy=False):
		self.clearPluginList()
		self.readPluginList(resolveFilename(SCOPE_PLUGINS))

	def shutdown(self):
		for p in self.pluginList[:]:
			self.removePlugin(p)

	def resetWarnings(self):
		self.warnings = []

	def getNextWakeupTime(self):
		wakeup = -1
		for p in self.pluginList:
			current = p.getWakeupTime()
			if current > -1 and (wakeup > current or wakeup == -1):
				wakeup = current
		return int(wakeup)


plugins = PluginComponent()
