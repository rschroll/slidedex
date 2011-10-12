import os
import sys
import subprocess
import tempfile
import glob
import gtk
import glib
import poppler
import cairo
import pango
import gtksourceview2 as sourceview
import vte

SEP = "\n%%SLIDEEDIT%%\n"
LATEXLANG = sourceview.language_manager_get_default().get_language('latex')
SCRIPTPATH = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))

def do_latex(obj, callback=None, stop_on_error=True):
    if obj.filename.endswith('.tex'):
        fn = obj.filename[:-4]
    else:
        fn = obj.filename
    
    def after_latex(status):
        if status == 0:
            obj.doc = poppler.document_new_from_file('file://' + os.path.abspath(fn+'.pdf'), None)
        if callback:
            callback(status)
    
    executor.add((("latex", "-halt-on-error", fn), ("dvips", fn), ("ps2pdf", fn+'.ps')),stop_on_error, (after_latex,))

class CommandExecutor(object):
    def __init__(self):
        self.is_running = False
        self.command_queue = []
        
        self.window = gtk.Window()
        vbox = gtk.VBox()
        self.window.add(vbox)
        hbox = gtk.HBox()
        vbox.pack_start(hbox)
        self.term = vte.Terminal()
        hbox.pack_start(self.term)
        hbox.pack_start(gtk.VScrollbar(self.term.get_adjustment()), False)
        self.term.set_scrollback_lines(1000)
        
        hbox = gtk.HBox()
        vbox.pack_start(hbox, expand=False, padding=6)
        self.label = gtk.Label('Hi')
        self.button = gtk.Button('Close')
        self.button.connect('clicked', self.on_close)
        hbox.pack_start(self.label, True, False)
        hbox.pack_end(self.button, False)
        vbox.show_all()
        self.window.connect('delete-event', self.on_close)
        self.term.connect('child-exited', self.callback)
        self.window.set_transient_for(doc.window)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.set_resizable(False)
    
    def add(self, commands, stop_on_error=True, callback=None):
        self.command_queue.append([commands, stop_on_error, callback])
        if not self.is_running:
            self.is_running = True
            self.window.show()
            self.label.set_text('Running')
            self.window.set_title('Running')
            self.button.set_sensitive(False)
            self.term.reset(True, True)
            self.run()
    
    def run(self):
        try:
            commands, stop_on_error, callback = self.command_queue[0]
        except IndexError:
            self.is_running = False
            self.window.hide()
            return
        try:
            command = commands[0]
            self.command_queue[0][0] = commands[1:]
        except IndexError:
            self.command_queue.pop(0)
            self.run()
        else:
            pid = self.term.fork_command(command[0], command)
    
    def callback(self, term):
        status = term.get_child_exit_status()
        commands, stop_on_error, callback = self.command_queue[0]
        
        if status != 0 or not commands:
            self.command_queue.pop(0)
            if callback:
                callback[0](status, *callback[1:])
        if status == 0 or not stop_on_error:
            self.run()
        else:
            self.error()
    
    def error(self):
        self.command_queue = []
        self.is_running = False
        self.label.set_text('Errors')
        self.window.set_title('Errors')
        self.button.set_sensitive(True)
        self.button.grab_focus()
    
    def on_close(self, widget, event=None):
        self.window.hide()
        return True


def render_to_pixbuf(page, msize):
    psize = page.get_size() # floats
    scale = min([s/ps for s, ps in zip(msize, psize)])
    size = [int(ps*scale) for ps in psize]
    pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, *size)
    page.render_to_pixbuf(0,0,size[0],size[1],scale,0,pb)
    return pb
    

class EventDispatcher(object):
    def __init__(self, parent):
        self.parent = parent
    
    def __getattr__(self, name):
        ob, sep, shname = name.partition('.')
        if shname:
            return getattr(getattr(self.parent, ob), shname)
        else:
            return getattr(self.parent, name)
        
class PDFViewer(object):
    def __init__(self, builder):
        self.prev_button = builder.get_object("prev_button")
        self.next_button = builder.get_object("next_button")
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_GO_BACK, gtk.ICON_SIZE_BUTTON)
        self.prev_button.set_image(image)
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_BUTTON)
        self.next_button.set_image(image)
        self.npage_label = builder.get_object("npage_label")
        self.page_entry = builder.get_object("page_entry")
        self.view_image = builder.get_object("view_image")
        self.doc = None
        self.npages = -1
        self.currpage = -1
    
    def _load(self):
        if self.doc is not None:
            self.npages = self.doc.get_n_pages()
            self.npage_label.set_text(" of %i"%self.npages)
            self.currpage = 0
            self.page_entry.set_sensitive(True)
        else:
            self.npages = 0
            self.npage_label.set_text("")
            self.page_entry.set_sensitive(False)
        self.set_page_controls()
    
    def load_file(self, filename):
        self.doc = poppler.document_new_from_file('file://' + os.path.abspath(filename), None)
        self._load()
    
    def load_doc(self, doc):
        self.doc = doc
        self._load()
        
    def on_prev(self, widget):
        self.currpage -= 1
        if self.currpage < 1:
            self.currpage = 0
        self.set_page_controls()
    
    def on_next(self, widget):
        self.currpage += 1
        self.set_page_controls()
    
    def on_setpage(self, widget):
        try:
            self.currpage = int(widget.get_text())-1
        except ValueError:
            pass
        self.set_page_controls()
    
    def set_page_controls(self):
        if self.currpage <= 0:
            self.currpage = 0
            self.prev_button.set_sensitive(False)
        else:
            self.prev_button.set_sensitive(True)
        if self.currpage >= self.npages-1:
            self.currpage = self.npages - 1
            self.next_button.set_sensitive(False)
            if self.currpage == 0:
                self.prev_button.set_sensitive(False)
        else:
            self.next_button.set_sensitive(True)
        self.page_entry.set_text(str(self.currpage+1))
        self.render()
    
    def render(self):
        if self.doc is not None:
            rect = self.view_image.get_allocation()
            pb = render_to_pixbuf(self.doc.get_page(self.currpage), (rect.width, rect.height))
            self.view_image.set_from_pixbuf(pb)
        else:
            self.view_image.set_from_icon_name(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)

class LatexDocument(object):
    def __init__(self, filename=None):
        builder = gtk.Builder()
        builder.add_from_file(os.path.join(SCRIPTPATH, "mainwindow.glade"))
        self.get_objects(builder)
        vbox = builder.get_object("vbox1")
        hbox = builder.get_object("hbox1")
        menu, toolbar, slidebar = self.set_actions()
        vbox.pack_end(toolbar, False)
        vbox.pack_end(menu, False)
        hbox.pack_end(slidebar, False)
        self.viewer = PDFViewer(builder)
        builder.connect_signals(EventDispatcher(self))
        
        self.header = LatexSlide(self, render=False)
        self.footer = LatexSlide(self, render=False)
        self.header_view = sourceview.View(self.header.buffer)
        builder.get_object("scrolledwindow1").add(self.header_view)
        self.currslide_view = sourceview.View()
        builder.get_object("scrolledwindow2").add(self.currslide_view)
        #self.empty_buffer = self.currslide_view.get_buffer()
        self.currslide_view.set_sensitive(False)
        self.footer_view = sourceview.View(self.footer.buffer)
        builder.get_object("scrolledwindow3").add(self.footer_view)
        font_desc = pango.FontDescription('monospace')
        for view in (self.header_view, self.currslide_view, self.footer_view):
            view.set_wrap_mode(gtk.WRAP_WORD_CHAR)
            if font_desc:
                view.modify_font(font_desc)
            view.show()
        self.notebook.set_current_page(1)

        self.pages = gtk.ListStore(object, gtk.gdk.Pixbuf)
        self.pages.connect('row-inserted', self.on_row_inserted)
        self.pages.connect('row-deleted', self.on_row_deleted)
        self.pages.connect('rows-reordered', self.on_rows_reordered)
        self.slidelist_view.set_model(self.pages)
        self.slidelist_view.set_pixbuf_column(1)
        self.slidelist_view.set_columns(1000)
        self.filename = filename
        self.doc = None
        if filename is not None:
            glib.idle_add(self.load, filename)
    
    def load(self, filename):
        dir = os.path.dirname(os.path.abspath(filename))
        os.chdir(dir)
        f = file(os.path.basename(filename), 'r')
        self._load(f)
    
    def _load(self, fobj):
        str = fobj.read()
        segments = str.split(SEP)
        if len(segments) < 2:
            raise IOError, "Could not load from file"
        self.pages.clear()
        self.header.set_content(segments[0])
        self.footer.set_content(segments[-1])
        for s in segments[1:-1]:
            self.add_page(s)
        self.compile(lambda status: self.slidelist_view.select_path((0,)))
    
    def add_page(self, content="", after=None):
        slide = LatexSlide(self, content, render=(content is not ""))
        if after is not None:
            self.pages.insert_after(after, (slide, slide.pb))
        else:
            self.pages.append((slide, slide.pb))
    
    def _save(self, fobj):
        fobj.write(self.header.get_content())
        for p in self.pages:
            fobj.write(SEP + p[0].get_content())
        fobj.write(SEP + self.footer.get_content())
    
    def save(self):
        if self.filename is None:
            raise NotImplementedError, "Need .filename to be set to save"
        f = file(self.filename, 'w')
        self._save(f)
        f.close()
        self.set_modified(False)
    
    def set_modified(self, mod):
        for p in self.pages:
            p[0].set_modified(mod)
        self.header.set_modified(mod)
        self.footer.set_modified(mod)
    
    def get_modified(self):
        for p in self.pages:
            if p[0].get_modified():
                return True
        return self.header.get_modified() or self.footer.get_modified()
    
    def on_modified_changed(self, buffer):
        name = self.filename or "Unnamed Presentation"
        if self.get_modified():
            self.window.set_title(name + '*')
        else:
            self.window.set_title(name)
    
    def compile(self, callback=None, stop_on_error=True):
        self.save()
        do_latex(self, callback, stop_on_error)
    
    def get_objects(self, builder):
        for object in ("window", 
                       "notebook",
                       "view_slide_button", 
                       "view_presentation_button",
                       "slidelist_view"):
            setattr(self, object, builder.get_object(object))
    
    def set_actions(self):
        UI_STRING = """
        <ui>
            <menubar name="TopMenu">
                <menu action="file">
                    <menuitem action="new"/>
                    <menuitem action="open"/>
                    <menuitem action="save"/>
                    <separator/>
                    <menuitem action="quit"/>
                </menu>
                <menu action="compile">
                    <menuitem action="compile-page"/>
                    <menuitem action="compile-all"/>
                </menu>
                <menu action="slide">
                    <menuitem action="next-slide"/>
                    <menuitem action="prev-slide"/>
                </menu>
            </menubar>
            <toolbar name="ToolBar" action="toolbar">
                <placeholder name="JustifyToolItems">
                    <separator/>
                    <toolitem action="new"/>
                    <toolitem action="open"/>
                    <separator/>
                    <toolitem action="compile-page"/>
                    <toolitem action="compile-all"/>
                    <separator/>
                </placeholder>
            </toolbar>
            <toolbar name="SlideBar" action="toolbar">
                <separator/>
                <toolitem action="new"/>
                <toolitem action="prev-slide"/>
                <toolitem action="next-slide"/>
                <separator/>
            </toolbar>
        </ui>"""
        
        action_group = gtk.ActionGroup("main")
        action_group.add_actions([
                ('file',    None,       "_File"),
                ('toolbar', None,       "Huh?"),
                ('new',     gtk.STOCK_NEW,  "_New Slide",   "<control>n",   None, self.on_new_slide),
                ('open',    gtk.STOCK_OPEN, "_Open in Tab", "<control>o",   None, self.blah),
                ('save',    gtk.STOCK_SAVE, "_Save",        "<control>s",   None, self.on_save),
                ('quit',    gtk.STOCK_QUIT, None,           "<control>w",   None, self.on_quit),
                
                ('compile', None,       "_Compile"),
                ('compile-page',    gtk.STOCK_CONVERT, "Compile Page", "<shift>Return", "Compile Page", self.on_compile_page),
                ('compile-all',     gtk.STOCK_EXECUTE, "Compile Document", "<control><shift>Return", "Compile Document", self.on_compile_all),
                
                ('slide',  None,   "_Slide"),
                ('next-slide',  gtk.STOCK_GO_FORWARD, "Next Slide",       "Page_Down",     None, self.on_next_slide),
                ('prev-slide',  gtk.STOCK_GO_BACK,    "Previous Slide",   "Page_Up",       None, self.on_prev_slide),
        ])
        
        #action = action_group.get_action('new')
        #action.connect_proxy(newbutton)
        
        ui_manager = gtk.UIManager()
        ui_manager.insert_action_group(action_group)
        ui_manager.add_ui_from_string(UI_STRING)
        ui_manager.ensure_update()
        self.window.add_accel_group(ui_manager.get_accel_group())
        slidebar = ui_manager.get_widget("/SlideBar")
        slidebar.set_orientation(gtk.ORIENTATION_VERTICAL)
        slidebar.set_style(gtk.TOOLBAR_ICONS)
        slidebar.set_property('icon-size', gtk.ICON_SIZE_BUTTON) #MENU)
        return ui_manager.get_widget("/TopMenu"), ui_manager.get_widget("/ToolBar"), slidebar
    
    def on_window_delete(self, widget, event):
        if self.get_modified():
            dialog = gtk.MessageDialog(self.window, 
                        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                        gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE)
            dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                               gtk.STOCK_QUIT, gtk.RESPONSE_NO,
                               gtk.STOCK_SAVE, gtk.RESPONSE_YES)
            dialog.set_default_response(gtk.RESPONSE_YES)
            dialog.set_markup("<big><b>Unsaved Changes</b></big>\n\nThe presentation has unsaved changes.")
            dialog.show_all()
            response = dialog.run()
            dialog.destroy()
            if response in (gtk.RESPONSE_REJECT, gtk.RESPONSE_DELETE_EVENT):
                return True
            if response == gtk.RESPONSE_YES:
                self.save()
        return False
    
    def on_window_destroy(self, widget, data=None):
        for p in self.pages:
            p[0].del_files()
        gtk.main_quit()
    
    def on_quit(self, action):
        if not self.on_window_delete(None, None):
            self.window.destroy()
    
    def on_save(self, action):
        self.save()
    
    def on_view_slide(self, widget):
        if widget.get_active():
            selection = self.slidelist_view.get_selected_items()[0]
            # This should be okay except for weird race conditions....
            currslide, = self.pages.get(self.pages.get_iter(selection), 0)
            self.viewer.load_doc(currslide.doc)
    
    def on_view_presentation(self, widget):
        if widget.get_active():
            self.viewer.load_doc(self.doc)
    
    def on_selection_changed(self, view):
        selection = view.get_selected_items()
        if len(selection) == 0 and self.prev_selection:
            view.select_path(self.prev_selection)
        elif len(selection) == 1:
            currslide, = self.pages.get(self.pages.get_iter(selection[0]), 0)
            self.currslide_view.set_buffer(currslide.buffer)
            self.currslide_view.set_sensitive(True)
            self.prev_selection = selection[0]
            if self.view_slide_button.get_active():
                self.viewer.load_doc(currslide.doc)
        else:
            self.currslide_view.set_sensitive(False)
    
    # Right now, these two are used by drag-and-drop reordering
    def on_row_inserted(self, model, path, iter):
        self.prev_selection = path
    
    def on_row_deleted(self, model, path):
        if path[0] < self.prev_selection[0]:
            self.prev_selection = (self.prev_selection[0] - 1,)
    
    def on_rows_reordered(self, model, path, iter, new_order):
        print "Reordered:", path, new_order
    
    def on_new_slide(self, action):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[0]
            iter = self.pages.get_iter(selection)
        else:
            iter = None
        self.add_page(after=iter)
        self.slidelist_view.unselect_all()
        self.slidelist_view.select_path((selection[0]+1,))#### selection + 1
        # Switch to slide editor and focus
        self.notebook.set_current_page(1)
        self.currslide_view.grab_focus()
    
    def on_compile_page(self, action):
        selection = self.slidelist_view.get_selected_items()
        if len(selection) == 1:
            currslide, = self.pages.get(self.pages.get_iter(selection[0]), 0)
            def callback(status):
                if status == 0:
                    currslide.render_thumb()
                    self.view_slide_button.clicked()
            currslide.compile(callback)
    
    def on_compile_all(self, action):
        self.save()
        self.compile(lambda status: not status and self.view_presentation_button.clicked())
    
    
    def on_next_slide(self, action):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[0][0]
            if selection < len(self.pages)-1:
                self.prev_selection = None
                self.slidelist_view.unselect_all()
                self.slidelist_view.select_path((selection+1,))
    
    def on_prev_slide(self, action):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[-1][0]
            if selection > 0:
                self.prev_selection = None
                self.slidelist_view.unselect_all()
                self.slidelist_view.select_path((selection-1,))
    
    def blah(self, action):
        print "Blah!"

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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = None
    doc = LatexDocument(filename)
    executor = CommandExecutor()
    doc.window.show()
    gtk.main()
