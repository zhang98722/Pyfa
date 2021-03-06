#!/usr/bin/env python
# ==============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of pyfa.
#
# pyfa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyfa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyfa.  If not, see <http://www.gnu.org/licenses/>.
# ==============================================================================

import sys
import os
import os.path
import re
import config

from optparse import OptionParser, BadOptionError, AmbiguousOptionError

import logbook
from logbook import TimedRotatingFileHandler, Logger, StreamHandler, NestedSetup, FingersCrossedHandler, NullHandler, \
    CRITICAL, ERROR, WARNING, DEBUG, INFO
pyfalog = Logger(__name__)


class PassThroughOptionParser(OptionParser):
    """
    An unknown option pass-through implementation of OptionParser.

    OSX passes -psn_0_* argument, which is something that pyfa does not handle. See GH issue #423
    """
    def _process_args(self, largs, rargs, values):
        while rargs:
            try:
                OptionParser._process_args(self, largs, rargs, values)
            except (BadOptionError, AmbiguousOptionError) as e:
                pyfalog.error("Bad startup option passed.")
                largs.append(e.opt_str)


class LoggerWriter:
    def __init__(self, level):
        # self.level is really like using log.debug(message)
        # at least in my case
        self.level = level

    def write(self, message):
        # if statement reduces the amount of newlines that are
        # printed to the logger
        if message not in {'\n', '    '}:
            self.level(message.replace("\n", ""))

    def flush(self):
        # create a flush method so things can be flushed when
        # the system wants to. Not sure if simply 'printing'
        # sys.stderr is the correct way to do it, but it seemed
        # to work properly for me.
        self.level(sys.stderr)


# Parse command line options
usage = "usage: %prog [--root]"
parser = PassThroughOptionParser(usage=usage)
parser.add_option("-r", "--root", action="store_true", dest="rootsavedata", help="if you want pyfa to store its data in root folder, use this option", default=False)
parser.add_option("-w", "--wx28", action="store_true", dest="force28", help="Force usage of wxPython 2.8", default=False)
parser.add_option("-d", "--debug", action="store_true", dest="debug", help="Set logger to debug level.", default=False)
parser.add_option("-t", "--title", action="store", dest="title", help="Set Window Title", default=None)
parser.add_option("-s", "--savepath", action="store", dest="savepath", help="Set the folder for savedata", default=None)
parser.add_option("-l", "--logginglevel", action="store", dest="logginglevel", help="Set desired logging level [Critical|Error|Warning|Info|Debug]", default="Error")

(options, args) = parser.parse_args()

if options.logginglevel == "Critical":
    options.logginglevel = CRITICAL
elif options.logginglevel == "Error":
    options.logginglevel = ERROR
elif options.logginglevel == "Warning":
    options.logginglevel = WARNING
elif options.logginglevel == "Info":
    options.logginglevel = INFO
elif options.logginglevel == "Debug":
    options.logginglevel = DEBUG
else:
    options.logginglevel = ERROR

if not hasattr(sys, 'frozen'):

    if sys.version_info < (2, 6) or sys.version_info > (3, 0):
        print("Pyfa requires python 2.x branch ( >= 2.6 )\nExiting.")
        sys.exit(1)

    try:
        import wxversion
    except ImportError:
        wxversion = None
        print("Cannot find wxPython\nYou can download wxPython (2.8+) from http://www.wxpython.org/")
        sys.exit(1)

    try:
        if options.force28 is True:
            wxversion.select('2.8')
        else:
            wxversion.select(['3.0', '2.8'])
    except wxversion.VersionError:
        print("Installed wxPython version doesn't meet requirements.\nYou can download wxPython 2.8 or 3.0 from http://www.wxpython.org/")
        sys.exit(1)

    try:
        import sqlalchemy

        saVersion = sqlalchemy.__version__
        saMatch = re.match("([0-9]+).([0-9]+)([b\.])([0-9]+)", saVersion)
        if saMatch:
            saMajor = int(saMatch.group(1))
            saMinor = int(saMatch.group(2))
            betaFlag = True if saMatch.group(3) == "b" else False
            saBuild = int(saMatch.group(4)) if not betaFlag else 0
            if saMajor == 0 and (saMinor < 5 or (saMinor == 5 and saBuild < 8)):
                print("Pyfa requires sqlalchemy 0.5.8 at least  but current sqlalchemy version is %s\n"
                      "You can download sqlalchemy (0.5.8+) from http://www.sqlalchemy.org/".format(sqlalchemy.__version__))
                sys.exit(1)
        else:
            print("Unknown sqlalchemy version string format, skipping check")

    except ImportError:
        sqlalchemy = None
        print("Cannot find sqlalchemy.\nYou can download sqlalchemy (0.6+) from http://www.sqlalchemy.org/")
        sys.exit(1)

    # check also for dateutil module installed.
    try:
        # noinspection PyPackageRequirements
        import dateutil.parser  # noqa - Copied import statement from service/update.py
    except ImportError:
        dateutil = None
        print("Cannot find python-dateutil.\nYou can download python-dateutil from https://pypi.python.org/pypi/python-dateutil")
        sys.exit(1)

    logVersion = logbook.__version__.split('.')
    if int(logVersion[0]) < 1:
        print ("Logbook version >= 1.0.0 is recommended. You may have some performance issues by continuing to use an earlier version.")


if __name__ == "__main__":
    # Configure paths
    if options.rootsavedata is True:
        config.saveInRoot = True

    # set title if it wasn't supplied by argument
    if options.title is None:
        options.title = "pyfa %s%s - Python Fitting Assistant" % (config.version, "" if config.tag.lower() != 'git' else " (git)")

    config.debug = options.debug

    # Import everything
    # noinspection PyPackageRequirements
    import wx
    import os
    import os.path

    try:
        # convert to unicode if it is set
        if options.savepath is not None:
            options.savepath = unicode(options.savepath)
        config.defPaths(options.savepath)

        # Basic logging initialization

        # Logging levels:
        '''
        logbook.CRITICAL
        logbook.ERROR
        logbook.WARNING
        logbook.INFO
        logbook.DEBUG
        logbook.NOTSET
        '''

        if options.debug:
            savePath_filename = "Pyfa_debug.log"
        else:
            savePath_filename = "Pyfa.log"

        savePath_Destination = os.path.join(config.savePath, savePath_filename)

        try:
            if options.debug:
                logging_mode = "Debug"
                logging_setup = NestedSetup([
                    # make sure we never bubble up to the stderr handler
                    # if we run out of setup handling
                    NullHandler(),
                    StreamHandler(
                        sys.stdout,
                        bubble=False,
                        level=options.logginglevel
                    ),
                    TimedRotatingFileHandler(
                        savePath_Destination,
                        level=0,
                        backup_count=3,
                        bubble=True,
                        date_format='%Y-%m-%d',
                    ),
                ])
            else:
                logging_mode = "User"
                logging_setup = NestedSetup([
                    # make sure we never bubble up to the stderr handler
                    # if we run out of setup handling
                    NullHandler(),
                    FingersCrossedHandler(
                        TimedRotatingFileHandler(
                            savePath_Destination,
                            level=0,
                            backup_count=3,
                            bubble=False,
                            date_format='%Y-%m-%d',
                        ),
                        action_level=ERROR,
                        buffer_size=1000,
                        # pull_information=True,
                        # reset=False,
                    )
                ])
        except:
            logging_mode = "Console Only"
            logging_setup = NestedSetup([
                # make sure we never bubble up to the stderr handler
                # if we run out of setup handling
                NullHandler(),
                StreamHandler(
                    sys.stdout,
                    bubble=False
                )
            ])

        import eos.db
        # noinspection PyUnresolvedReferences
        import service.prefetch  # noqa: F401

        # Make sure the saveddata db exists
        if not os.path.exists(config.savePath):
            os.mkdir(config.savePath)

        eos.db.saveddata_meta.create_all()

    except Exception, e:
        import traceback
        from gui.errorDialog import ErrorFrame

        tb = traceback.format_exc()

        pyfa = wx.App(False)
        ErrorFrame(e, tb)
        pyfa.MainLoop()
        sys.exit()

    with logging_setup.threadbound():
        # Don't redirect if frozen
        if not hasattr(sys, 'frozen'):
            # Output all stdout (print) messages as warnings
            try:
                sys.stdout = LoggerWriter(pyfalog.warning)
            except ValueError, Exception:
                pyfalog.critical("Cannot access log file.  Continuing without writing stdout to log.")

            if not options.debug:
                # Output all stderr (stacktrace) messages as critical
                try:
                    sys.stderr = LoggerWriter(pyfalog.critical)
                except ValueError, Exception:
                    pyfalog.critical("Cannot access log file.  Continuing without writing stderr to log.")

        pyfalog.info("Starting Pyfa")
        pyfalog.info("Running in logging mode: {0}", logging_mode)

        if hasattr(sys, 'frozen') and options.debug:
            pyfalog.critical("Running in frozen mode with debug turned on. Forcing all output to be written to log.")

        from gui.mainFrame import MainFrame

        pyfa = wx.App(False)
        MainFrame(options.title)
        pyfa.MainLoop()
