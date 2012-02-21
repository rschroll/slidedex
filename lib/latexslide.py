# Copyright 2010, 2011 Robert Schroll
#
# This file is part of SlideDeX and is distributed under the terms of
# the BSD license.  See the file COPYING for full details.
#
######################################################################

import os
import tempfile
import glob
import gtk
import gtksourceview2 as sourceview
from misc import SEP, render_to_pixbuf

LATEXLANG = sourceview.language_manager_get_default().get_language('latex')

class LatexSlide(object):
    
    def __init__(self, parent, content="", render=False):
        self.parent = parent
        self.buffer = sourceview.Buffer(language=LATEXLANG)
        self.set_content(content)
        self.buffer.connect("modified-changed", self.on_buffer_modified_changed)
        self.doc = None
        self.pb = self.parent.window.render_icon(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)
        self._filename = None
        self._modified_since_save = False
        self._modified_since_compile = True
        if render:
            self.compile(lambda status: not status and self.render_thumb(), False)
    
    @property
    def fullfilename(self):
        # Lazily create filename
        if not self._filename:
            # This is deprecated as a security risk, since the file could be
            # created before you make it.  But we're not actually using this
            # file; we're using the filename as a base, so the additional
            # features of mkstemp don't help us avoid this problem.
            filename = tempfile.mktemp(prefix='ztmp', dir=self.parent.dir)
            self._filename = os.path.basename(filename)
        return os.path.join(self.parent.dir, self._filename)
    
    def set_content(self, content=""):
        self.buffer.begin_not_undoable_action()
        self.buffer.set_text(content)
        self.buffer.end_not_undoable_action()
        self.buffer.set_modified(False)
        self.buffer.place_cursor(self.buffer.get_start_iter())
    
    def get_content(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter())
    
    def on_buffer_modified_changed(self, buffer):
        if buffer.get_modified():
            self.modified_since_save = True
            self.modified_since_compile = True
    
    @property
    def modified_since_save(self):
        return self._modified_since_save
    
    @modified_since_save.setter
    def modified_since_save(self, value):
        self._modified_since_save = value
        if value == False:
            self.buffer.set_modified(False)
        self.parent.on_modified_changed()
    
    @property
    def modified_since_compile(self):
        return self._modified_since_compile
    
    @modified_since_compile.setter
    def modified_since_compile(self, value):
        self._modified_since_compile = value
        if value == False:
            self.buffer.set_modified(False)
    
    def compile(self, callback=None, stop_on_error=True):
        f = file(self.fullfilename + '.tex', 'w')
        f.write(self.parent.header.get_content() + SEP + self.get_content() +
                SEP + self.parent.footer.get_content())
        f.close()
        self.modified_since_compile = False
        self.do_latex(callback, stop_on_error)
    
    def do_latex(self, callback, stop_on_error):
        self.parent._do_latex(self, self.parent.settings.slide_command, callback, stop_on_error)
    
    def render_thumb(self):
        if self.doc is not None:
            self.pb = render_to_pixbuf(self.doc.get_page(0), (300,100))
        else:
            self.pb = self.parent.window.render_icon(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)
        for i in range(len(self.parent.pages)):
            if self.parent.pages[i][0] == self:
                self.parent.pages[i][1] = self.pb
    
    def del_files(self):
        if self._filename:
            for f in glob.glob(self.fullfilename + '*'):
                os.unlink(f)

class HeaderFooter(LatexSlide):
    
    @property
    def modified_since_compile(self):
        return None  # This won't be called.
    
    @modified_since_compile.setter
    def modified_since_compile(self, value):
        if value:
            for p,_ in self.parent.pages:
                p.modified_since_compile = True
            # Make sure we get notified the next time it changes.
            self.buffer.set_modified(False)
