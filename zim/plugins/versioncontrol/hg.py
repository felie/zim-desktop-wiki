# -*- coding: utf-8 -*-

# Copyright 2009 Jaap Karssenberg <pardus@cpan.org>

from __future__ import with_statement

import os
import logging

from zim.fs import FS
from zim.applications import Application
from zim.async import AsyncOperation
from zim.plugins.versioncontrol import NoChangesError
from zim.plugins.versioncontrol.generic import VersionControlSystemBackend

logger = logging.getLogger('zim.vcs.hg')

# TODO document API - use base class
class HG(object):
	#FIXME Bin = 'hg'
	App = Application(('hg',))
	
	def __init__(self, root):
		self._app = Application(('hg',))
		self.root = root
		
	@classmethod
	def tryexec(cls):
		return HG.App.tryexec()
	
	def run(self, params):
		return self._app.run(params, self.root)

	def pipe(self, params):
		return self._app.pipe(params, self.root)

	def build_revision_arguments(self, versions):
		"""Build a list including required string/int for running an VCS command
		# Accepts: None, int, string, (int,), (int, int)
		# Always returns a list
		# versions content:
		  - None: return an empty list
		  - int ou string: return ['-r', int]
		  - tuple or list: return ['-r', '%i..%i']
		  
		It's all based on the fact that defining revision with current VCS is:
		-r revision
		-r rev1..rev2
		"""
		if isinstance(versions, (tuple, list)):
			assert 1 <= len(versions) <= 2
			if len(versions) == 2:
				versions = map(int, versions)
				versions.sort()
				return ['-r', '%i..%i' % tuple(versions)]
			else:
				versions = versions[0]

		if not versions is None:
			version = int(versions)
			return ['-r', '%i' % version]
		else:
			return []

	def _ignored(self, path):
		"""return True if the path should be ignored by the version control system
		"""
		return False


	########
	#
	# NOW ARE ALL REVISION CONTROL SYSTEM SHORTCUTS
	
	def add(self, path=None):
		"""
		Runs: hg add {{PATH}}
		"""
		if path is None:
			return self.run(['add'])
		else:
			return self.run(['add', path])
		

	def annotate(self, file, version):
		"""FIXME Document
		return
		0: line1
		2: line1
		...
		"""
		revision_args = self.build_revision_arguments(version)
		return self.pipe(['annotate', file] + revision_args)

	def cat(self, path, version):
		"""
		Runs: hg cat {{PATH}} {{REV_ARGS}}
		"""
		revision_args = self.build_revision_arguments(version)
		return self.pipe(['cat', path] + revision_args)

	def commit(self, path, msg):
		"""
		Runs: hg commit -m {{MSG}} {{PATH}}
		"""
		params = ['commit']
		if msg!='' and msg!=None:
			params.append('-m')
			params.append(msg)
		if path!='' and path!=None:
			params.append(path)
		return self.run(params)
			
	def diff(self, versions, path=None):
		"""
		Runs:
			hg diff --git {{REVISION_ARGS}} 
		or
			hg diff --git {{REVISION_ARGS}} {{PATH}}
		"""
		revision_args = self.build_revision_arguments(versions)
		if path==None:
			return self.pipe(['diff', '--git'] + revision_args)
			# Using --git option allow to show the renaming of files
		else:
			return self.pipe(['diff', '--git', path] + revision_args)

	def ignore(self, file_to_ignore_regexp):
		"""
		Build a .hgignore file including the file_to_ignore_content
		"""
		root = self.root.__str__()
		hgignore_filepath = os.path.join(root, '.hgignore')
		hgignore_fh = open(hgignore_filepath, 'w')
		hgignore_fh.write(file_to_ignore_regexp)
		hgignore_fh.close()

	def init_repo(self):
		self.init()
		self.ignore('\.zim*$\n')
		self.add('.') # add all existing files

	def init(self):
		"""
		Runs: hg init
		"""
		return self.run(['init'])

	def log(self, path=None):
		"""
		Runs: hg log -r : --verbose {{PATH}}
		the "-r :" option allows to reverse order
		--verbose allows to get the entire commit message
		"""
		if path:
			return self.pipe(['log', '-r', ':', '--verbose', path])
		else:
			return self.pipe(['log', '-r', ':', '--verbose'])

	def log_to_revision_list(self, log_op_output):
		versions = []
		(rev, date, user, msg) = (None, None, None, None)
		seenmsg = False
		# seenmsg allow to get the complete commit message which is presented like this:
		#
		# [...]
		# description:
		# here is the
		# commit message
		# the end of it may be detected
		# because of the apparition of a line
		# starting by "changeset:"
		#
		# FIXME: there is a bug which will stop parsing if a blank line is included
		# in the commit message
		for line in log_op_output:
			if len(line.strip())==0:
				if not rev is None:
					versions.append((rev, date, user, msg))
				(rev, date, user, msg) = (None, None, None, None)
				seenmsg = False
			elif line.startswith('changeset: '):
				logger.info("LINE IS #%s#" % line)
				value = line[13:].strip()
				logger.info("THE REV. IS #%s#" % value)
				# In case of mercurial, the revision number line
				# is something like this:
				# changeset:   6:1d4a428e22d9
				#
				# instead of (for bzr) like that:
				# e.g. "revno: 48 [merge]\n"
				value = value.split(":")[0]
				rev = int(value)
			elif line.startswith('user: '):
				user = line[13:].strip()
			elif line.startswith('date: '):
				date = line[13:].strip()
			elif line.startswith('description:'):
				seenmsg = True
				msg = u''
			elif seenmsg:
				msg += line

		if not rev is None:
			versions.append((rev, date, user, msg))

		return versions


	def move(self, oldpath, newpath):
		"""
		Runs: hg mv --after {{OLDPATH}} {{NEWPATH}}
		"""
		return self.run(['mv', '--after', oldpath, newpath])

	def remove(self, path):
		"""
		Runs: hg rm {{PATH}}
		"""
		return self.run(['rm', path])

	def revert(self, path, version):
		"""
		Runs:
			hg revert --no-backup {{PATH}} {{REV_ARGS}}
		or
			hg revert --no-backup --all {{REV_ARGS}}
		"""
		revision_params = self.build_revision_arguments(version)
		if path:
			return self.run(['revert', '--no-backup', path] + revision_params)
		else:
			return self.run(['revert', '--no-backup', '--all'] + revision_params)

	def status(self):
		"""
		Runs: hg status
		"""
		return self.pipe(['status'])


class MercurialVCS(VersionControlSystemBackend):
	
	def __init__(self, dir):
		vcs_app = HG(dir)
		super(MercurialVCS, self).__init__(dir, vcs_app)

	@classmethod
	def _check_dependencies(klass):
		"""@see VersionControlSystemBackend.check_dependencies"""
		return HG.tryexec()

