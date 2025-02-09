# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor

#------------------------------------------------------------------------------------------


def Pic_Thumb(*args, **kwa):
	from . import ui
	return ui.Pic_Thumb(*args, **kwa)


def picshow(*args, **kwa):
	from . import ui
	return ui.picshow(*args, **kwa)


def main(session, **kwargs):
	from .ui import picshow
	session.open(picshow)


def filescan_open(list, session, **kwargs):
	# Recreate List as expected by PicView
	for file in list:
		filelist = [((file.path, False), None) for file in list]
	from .ui import Pic_Full_View
	session.open(Pic_Full_View, filelist, 0, file.path)


def filescan(**kwargs):
	from Components.Scanner import Scanner, ScanPath
	from os.path import exists

	# Overwrite checkFile to only detect local
	class LocalScanner(Scanner):
		def checkFile(self, file):
			return exists(file.path)

	return \
		LocalScanner(mimetypes=["image/jpeg", "image/png", "image/gif", "image/bmp", "image/svg+xml"],
			paths_to_scan=[
					ScanPath(path="DCIM", with_subdirs=True),
					ScanPath(path="", with_subdirs=False),
				],
			name="Pictures",
			description=_("View photos..."),
			openfnc=filescan_open,
		)


def Plugins(**kwargs):
	return \
		[PluginDescriptor(name=_("Picture player"), description=_("fileformats (BMP, PNG, JPG, GIF)"), icon="pictureplayer.png", where=PluginDescriptor.WHERE_PLUGINMENU, needsRestart=False, fnc=main),
		PluginDescriptor(name=_("Picture player"), where=PluginDescriptor.WHERE_FILESCAN, needsRestart=False, fnc=filescan)]
