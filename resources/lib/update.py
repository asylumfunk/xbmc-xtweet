#
#Copyright (C) 2009  asylumfunk
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You may obtain a copy of this license at:
#  http://www.gnu.org/licenses/gpl-3.0.html

#Standard modules
import os
import sha
import sys
import threading
import urllib
import urllib2
#Third-party modules
import xbmc
import xbmcgui
from twitter import simplejson

FILE_BLOCK_SIZE = 1024

class DownloadProgressDialog( xbmcgui.DialogProgress ):
	"""A progress dialog for file downloads"""

	"""
	Description:
		Initializes the prompt's text
		Displays the prompt
	"""
	def __init__( self, heading = "", line1 = "", line2 = "", line3 = "" ):
		xbmcgui.DialogProgress.__init__( self )
		xbmcgui.DialogProgress.create( self, heading, line1, line2, line3 )

	"""
	Description:
		Updates the download's progress display
		Mimics urllib.urlretrieve's reporthook
	Args:
		blockNumber::int - number of blocks that have been downloaded
		blockSize::int - number of bytes per block
		totalSize::int - number of bytes in the file
	"""
	def update( self, blockNumber, blockSize, totalSize ):
		if self.iscanceled():
			percent = 100
		elif totalSize <= 0:
			percent = 0
		else:
			#calculates the percentage and ensures it is in the range (0-100)
			percent = max( min( int( blockNumber * blockSize * 100 / totalSize ), 100 ), 0 )
		xbmcgui.DialogProgress.update( self, percent )

class ThreadedDownload( threading.Thread ):
	"""Performs threaded file downloads"""

	"""
	Description:
		Initializes a new threaded download
	Args:
		url::string - URL to be downloaded
		directory::string - destination directory where download should be saved
		filename::string - filename used to save the download
		progressDialog::update.DownloadProgressDialog (optional) - dialog used to display the download's progress
	"""
	def __init__( self, url, directory, filename, progressDialog = None ):
		self.url = url
		self.directory = directory
		self.filename = filename
		self.progressDialog = progressDialog
		threading.Thread.__init__( self )

	"""
	Description:
		Downloads the URL and saves it locally
	"""
	def run( self ):
		try:
			if not os.path.isdir( self.directory ):
				os.makedirs( self.directory )
		except:
			return
		request = urllib2.Request( self.url )
		request.add_header( "User-Agent", "Mozilla/5.0 " \
									"(X11; U; Linux i686) Gecko/20    " \
									"071127 Firefox/2.0.0.11" )
		try:
			streamIn = urllib2.urlopen( request )
			try:
				totalSize = int( streamIn.info().get( 'Content-Length', 0 ) )
			except:
				totalSize = 0
			streamOut = open( os.path.join( self.directory, self.filename ), "wb" )
			i = 0
			while True:
				if self.progressDialog is not None and self.progressDialog.iscanceled():
					break
				i = i + 1
				block = streamIn.read( FILE_BLOCK_SIZE )
				if block == "":
					break
				streamOut.write( block )
				if self.progressDialog is not None:
					self.progressDialog.update( i, FILE_BLOCK_SIZE, totalSize )
			streamIn.close()
			streamOut.close()
		except:
			try:
				streamIn.close()
				streamOut.close()
			except:
				pass

class Update:
	"""Allows the project to update itself"""

	cfg = sys.modules[ "__main__" ].cfg

	"""
	Description:
		Default constructor
	"""
	def __init__( self ):
		self._currentVersion = sys.modules[ "__main__" ].__version__
		self._details = {}
		self._shouldCheckForUpdates = ( self.cfg.get( "update.checkForUpdates" ) or "True" ).lower() == "true"

	"""
	Description:
		Indicates whether or not an update requires a restart
	Returns:
		boolean result flag
	"""
	def requiresRestart( self ):
		return self._details.get( "requiresRestart", False )

	"""
	Descripton:
		Controls the auto-update flow
	TODO: i18n
	"""
	def tryUpdateProject( self ):
		if self._shouldCheckForUpdates:
			self._checkForUpdate()
			if self._isUpdateAvailable():
				if self._doesUserWantToUpdate():
					if self._update():
						if self.requiresRestart():
							self._alert( "update complete", "yayyyy!", "gotta reboot" )
						else:
							pass
							#reload cfg
							#reload i18n
						return True
		return False

	"""
	Description:
		Displays an alert to the user
	"""
	def _alert( self, heading, line1, line2 = "", line3 = "" ):
		alert = xbmcgui.Dialog()
		return alert.ok( heading, line1, line2, line3 )

	"""
	Description:
		Queries for update details
	TODO: include a unique identifier of some kind
	"""
	def _checkForUpdate( self ):
		queryParams = urllib.urlencode( { "currentVersion" : self._currentVersion } )
		url = self.cfg.get( "update.urlToCheck.format" ) % { "params" : queryParams }
		request = urllib2.Request( url = url )
		try:
			stream = urllib2.urlopen( request )
			json = stream.read()
			details = simplejson.loads( json )
		except:
			details = {}
		self._details = details

	"""
	Description:
		Prompts the user to see if they would like to update the project
		Assumes that an update exists
	Returns:
		boolean flag
	TODO: i18n
	"""
	def _doesUserWantToUpdate( self ):
		prompt = xbmcgui.Dialog()
		return prompt.yesno( "Update available: verison 1.5", "A new version of xTweet is available.", "Would you like to update?" )

	"""
	Description:
		Downloads the update to the local updates directory
	Args:
		url::string - URL of the update file
	Returns:
		Success - str:: - local filename of the downloaded update
		Failure - None
	TODO: i18n
	TODO: make xbmc.sleep(...) time a constant
	TODO: make urlDeliminator a constant (?)
	"""
	def _download( self, url ):
		try:
			urlDeliminator = "/"
			urlParts = url.split( urlDeliminator )
			urlDirectory = urlDeliminator.join( urlParts[ 0 : -1 ] ) + urlDeliminator
			filename = urlParts[ -1 ]
			localDirectory= sys.modules[ "__main__" ].UPDATES_DIRECTORY
			localPath = os.path.join( localDirectory, filename )
			progressDialog = DownloadProgressDialog( "Updating", "downloading...", urlDirectory, filename )
			download = ThreadedDownload( url, localDirectory, filename, progressDialog )
			download.start()
			while download.isAlive():
				if progressDialog.iscanceled():
					break
				xbmc.sleep( 500 )
			progressDialog.close()
		except:
			localPath = None
		return localPath

	#TODO: abstract to auto-detect compression type
	def _extractArchive( self, file, destination ):
		try:
			import tarfile
			tarball = tarfile.open( name = file, mode = "r:gz" )
			for tar in tarball:
				tarball.extract( tar, destination )
			tarball.close()
			return True
		except:
			try:
				tarball.close()
			except:
				pass
			return False

	"""
	Description:
		Calculates the SHA-1 checksum of a file
	Args:
		filename::string - absolute path of the file in question
	Returns:
		Success::str - the file's SHA-1 checksum
		Failure::None
	"""
	def _getSha1Checksum( self, filename ):
		try:
			file = open( filename, "rb" )
			hash = sha.new()
			while True:
				block = file.read( FILE_BLOCK_SIZE )
				if block == "":
					break
				hash.update( block )
			file.close()
			checksum = hash.hexdigest()
		except:
			try:
				file.close()
			except:
				pass
			checksum = None
		return checksum

	"""
	Description:
		Indicates whether or not an update is available
	Returns:
		boolean result flag
	"""
	def _isUpdateAvailable( self ):
		return self._details.get( "isUpdateAvailable", False )

	"""
	Description:
		Attempts to update the project
	Returns:
		boolean success flag
	TODO: remove logical short-circuits
	TODO: i18n
	"""
	def _update( self ):
		url = str( self._details.get( "downloadUrl", "" ) )
		if url:
			file = self._download( url )
			if file and os.path.isfile( file ):
				expectedChecksum = self._details.get( "sha1checksum", None )
				receivedChecksum = self._getSha1Checksum( file )
				if True or receivedChecksum and receivedChecksum == expectedChecksum:
					scriptDirectory = os.path.join( sys.modules[ "__main__" ].PROJECT_DIRECTORY, os.pardir )
					if True or self._extractArchive( file, scriptDirectory ):
						return True
				else:
					print "checksum mismatch"
			else:
				return "download failed"
		else:
			print "invalid url"
		self._alert( "Warning", "The update could not be successfully completed." )
		return False