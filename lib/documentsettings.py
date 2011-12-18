# Copyright 2011 Robert Schroll
#
# This file is part of SlideDeX and is distributed under the terms of
# the BSD license.  See the file COPYING for full details.
#
######################################################################

import ConfigParser
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from StringIO import StringIO

DEFAULT_COMMAND = 'latex -halt-on-error {fn}; dvips {fn}; ps2pdf {fn}.ps'

class SettingsError(Exception):
    pass

class DocumentSettings(object):
    
    def __init__(self, input_string):
        self.parser = ConfigParser.RawConfigParser(dict_type=OrderedDict)
        self.parser.add_section('commands')
        self.parser.set('commands', 'slide', DEFAULT_COMMAND)
        self.parser.set('commands', 'presentation', DEFAULT_COMMAND)
        self.parser.add_section('skeletons')
        self.load(input_string)
    
    def load(self, input_string):
        settings_string = StringIO()
        for line in input_string.split('\n'):
            if line.startswith('% '):
                settings_string.write(line[2:] + '\n')
            else:
                raise SettingsError, "Invalid line start"
        settings_string.seek(0)
        self.parser.readfp(settings_string)
    
    def write(self):
        settings_string = StringIO()
        self.parser.write(settings_string)
        settings_string.seek(0)
        output = ['% ' + line for line in settings_string]
        return ''.join(output)
    
    @property
    def slide_command(self):
        return self.parser.get('commands', 'slide')
    
    @property
    def pres_command(self):
        return self.parser.get('commands', 'presentation')
    
    @property
    def skeletons(self):
        skels = OrderedDict(self.parser.items('skeletons'))
        if not 'blank' in skels:
            skels['blank'] = ''
        return skels
