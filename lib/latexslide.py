import os
import tempfile
import glob
import gtk
import gtksourceview2 as sourceview
from misc import SEP, do_latex, render_to_pixbuf

LATEXLANG = sourceview.language_manager_get_default().get_language('latex')

class LatexSlide(object):
    
    def __init__(self, parent, content="", render=True):
        self.parent = parent
        self.buffer = sourceview.Buffer(language=LATEXLANG)
        self.set_content(content)
        self.buffer.connect("modified-changed", self.parent.on_modified_changed)
        # This is deprecated as a security risk, since the file could be
        # created before you make it.  But we're not actually using this
        # file; we're using the filename as a base, so the additional
        # features of mkstemp don't help us avoid this problem.
        filename = tempfile.mktemp(dir='./')
        self.filename = os.path.basename(filename)
        self.doc = None
        self.pb = self.parent.window.render_icon(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)
        if render:
            self.compile(lambda status: not status and self.render_thumb(), False)
    
    def set_content(self, content=""):
        self.buffer.begin_not_undoable_action()
        self.buffer.set_text(content)
        self.buffer.end_not_undoable_action()
        self.buffer.set_modified(False)
        self.buffer.place_cursor(self.buffer.get_start_iter())
    
    def get_content(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter())
    
    def set_modified(self, mod):
        self.buffer.set_modified(mod)
    
    def get_modified(self):
        return self.buffer.get_modified()
    
    def compile(self, callback=None, stop_on_error=True):
        f = file(self.filename + '.tex', 'w')
        f.write(self.parent.header.get_content() + SEP + self.get_content() + 
                SEP + self.parent.footer.get_content())
        f.close()
        do_latex(self, callback, stop_on_error)
    
    def render_thumb(self):
        if self.doc is not None:
            self.pb = render_to_pixbuf(self.doc.get_page(0), (300,100))
        else:
            self.pb = self.parent.window.render_icon(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)
        for i in range(len(self.parent.pages)):
            if self.parent.pages[i][0] == self:
                self.parent.pages[i][1] = self.pb
    
    def del_files(self):
        for f in glob.glob(self.filename + '*'):
            os.unlink(f)

