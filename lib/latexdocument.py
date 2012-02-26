# Copyright 2010, 2011 Robert Schroll
#
# This file is part of SlideDeX and is distributed under the terms of
# the BSD license.  See the file COPYING for full details.
#
######################################################################

import os
import sys
import gtk
import glib
import pango
import poppler
import gtkspell
import gtksourceview2 as sourceview
from misc import SEP, LIBPATH
from pdfviewer import PDFViewer
from latexslide import LatexSlide, HeaderFooter
from commandexecutor import CommandExecutor
from documentsettings import DocumentSettings


class ObstinateUserError(Exception):
    pass


def base_filename(fn):
    if fn.endswith('.tex'):
        return fn[:-4]
    else:
        return fn


class EventDispatcher(object):
    def __init__(self, parent):
        self.parent = parent
    
    def __getattr__(self, name):
        ob, sep, shname = name.partition('.')
        if shname:
            return getattr(getattr(self.parent, ob), shname)
        else:
            return getattr(self.parent, name)


class LatexDocument(object):
    
    SAME_WIDGET = 1000
    TEXT = 1001
    TARGETS = [('SLIDEDEX_SLIDE', gtk.TARGET_SAME_WIDGET, SAME_WIDGET),
               ('text/plain', 0, TEXT)]
    
    def __init__(self, filename=None):
        builder = gtk.Builder()
        builder.add_from_file(os.path.join(LIBPATH, "mainwindow.glade"))
        self.get_objects(builder)
        vbox = builder.get_object("vbox1")
        hbox = builder.get_object("hbox1")
        menu, toolbar, slidebar = self.set_actions()
        vbox.pack_end(toolbar, False)
        vbox.pack_end(menu, False)
        hbox.pack_end(slidebar, False)
        self.viewer = PDFViewer(builder)
        builder.connect_signals(EventDispatcher(self))
        
        self.settings = None
        self.header = HeaderFooter(self)
        self.footer = HeaderFooter(self)
        self.header_view = sourceview.View(self.header.buffer)
        gtkspell.Spell(self.header_view)
        builder.get_object("scrolledwindow1").add(self.header_view)
        self.currslide_view = sourceview.View()
        gtkspell.Spell(self.currslide_view)
        builder.get_object("scrolledwindow2").add(self.currslide_view)
        #self.empty_buffer = self.currslide_view.get_buffer()
        self.currslide_view.set_sensitive(False)
        self.footer_view = sourceview.View(self.footer.buffer)
        gtkspell.Spell(self.footer_view)
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
        
        self.slidelist_view.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, self.TARGETS, 
                                                     gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
        self.slidelist_view.enable_model_drag_dest(self.TARGETS,
                                                   gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
        self.slidelist_view.connect('drag-data-get', self.on_drag_data_get)
        self.slidelist_view.connect('drag-data-received', self.on_drag_data_received)
        
        self._filename = None
        self._dir = None
        self.doc = None
        self._loaded = True
        self._order_modified = False
        if filename is not None:
            glib.idle_add(self.load, filename)
        
        self.executor = CommandExecutor(self)
        
        self.window.show()
        gtk.main()
    
    @property
    def dir(self):
        if not self._dir:
            self.save_as()
        if self._dir:
            return self._dir
        raise ObstinateUserError, "C'mon, we need a filename"
    
    @property
    def fullfilename(self):
        return os.path.join(self.dir, self._filename)
    
    @fullfilename.setter
    def fullfilename(self, filename):
        self._dir = os.path.dirname(os.path.abspath(filename))
        self._filename = os.path.basename(filename)
    
    def load(self, filename):
        self.fullfilename = filename
        f = file(self.fullfilename, 'r')
        self._load(f)
    
    def _load(self, fobj):
        self._loaded = False
        if not fobj.readline().startswith(SEP[1:-1]):  # Skip newlines
            raise IOError, "Not a SlideDeX file"
        str = fobj.read()
        segments = str.split(SEP)
        if len(segments) < 3:
            raise IOError, "Could not load from file"
        self.settings = DocumentSettings(self, segments[0])
        self.pages.clear()
        self.header.set_content(segments[1])
        self.footer.set_content(segments[-1])
        for s in segments[2:-1]:
            self.add_page(s)
        
        pdffn = base_filename(self.fullfilename) + '.pdf'
        select_first_page = lambda status: self.slidelist_view.select_path((0,))
        if os.path.exists(pdffn) and os.stat(pdffn).st_mtime >= os.stat(self.fullfilename).st_mtime:
            self.compile_pages()
            self.doc = poppler.document_new_from_file('file://' + os.path.abspath(pdffn), None)
            self.executor.add_callback(select_first_page)
        else:
            self.compile(select_first_page)
        self._loaded = True
    
    def add_page(self, content="", after=None, before=None, render=False):
        slide = LatexSlide(self, content, render=(render and content))
        if after is not None:
            self.pages.insert_after(after, (slide, slide.pb))
        elif before is not None:
            self.pages.insert_before(before, (slide, slide.pb))
        else:
            self.pages.append((slide, slide.pb))
    
    def delete_page(self, iter):
        self.pages.remove(iter)
    
    def _save(self, fobj):
        fobj.write(SEP[1:])  # Skip initial newline
        fobj.write(self.settings.write())
        fobj.write(SEP[1:])  # Skip initial newline
        fobj.write(self.header.get_content())
        for p in self.pages:
            fobj.write(SEP + p[0].get_content())
        fobj.write(SEP + self.footer.get_content())
    
    def save(self):
        f = file(self.fullfilename, 'w')
        self._save(f)
        f.close()
        self.modified = False
    
    @property
    def modified(self):
        if self._order_modified or self.header.modified_since_save \
                or self.footer.modified_since_save:
            # Check these first since we set header as modified when the
            # slide ordering changes.  In that case, all of the pages
            # may not have their LatexSlides yet, so we want to short-
            # circuit here.
            return True
        for p in self.pages:
            if p[0].modified_since_save:
                return True
        return False
    
    @modified.setter
    def modified(self, mod):
        self._order_modified = mod
        self.on_modified_changed()  # We might not have a page that will call this.
        if mod:  # We only need to set one to True
            return
        self.header.modified_since_save = mod
        self.footer.modified_since_save = mod
        for p in self.pages:
            p[0].modified_since_save = mod
    
    def on_modified_changed(self):
        name = self._filename or "Unnamed Presentation"
        if self.modified:
            self.window.set_title(name + '*')
        else:
            self.window.set_title(name)
    
    def compile_pages(self):
        for p,_ in self.pages:
            if p.modified_since_compile:
                def pagecallback(status, page=p):  # Freeze p
                    if status == 0:
                        page.render_thumb()
                p.compile(pagecallback, False)
    
    def compile(self, callback=None, stop_on_error=True):
        self.compile_pages()
        if self.modified:
            self.save()
        self.do_latex(callback, stop_on_error)
    
    def do_latex(self, callback, stop_on_error):
        self._do_latex(self, self.settings.pres_command, callback, stop_on_error)
    
    def _do_latex(self, obj, command, callback, stop_on_error):
        # obj is either this LatexDocument or one of its LatexSlides
        fn = base_filename(obj.fullfilename)
        
        def after_latex(status):
            if status == 0:
                obj.doc = poppler.document_new_from_file('file://' + os.path.abspath(fn+'.pdf'), None)
            if callback:
                callback(status)
        
        commands = [[s.format(fn=fn) for s in c.split()] for c in command.split(';')]
        self.executor.add(commands, stop_on_error, (after_latex,))
    
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
                    <menuitem action="save-as"/>
                    <separator/>
                    <menuitem action="quit"/>
                </menu>
                <menu action="compile">
                    <menuitem action="compile-page"/>
                    <menuitem action="compile-all"/>
                </menu>
                <menu action="slide" name="Slide">
                    <menuitem action="new-slide-menu" name="NewSlide"/>
                    <menuitem action="delete-slide"/>
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
                <toolitem action="new-slide-toolbar"/>
                <toolitem action="delete-slide"/>
                <toolitem action="prev-slide"/>
                <toolitem action="next-slide"/>
                <separator/>
            </toolbar>
        </ui>"""
        
        action_group = gtk.ActionGroup("main")
        action_group.add_actions([
                ('file',    None,       "_File"),
                ('toolbar', None,       "Huh?"),
                ('new',     gtk.STOCK_NEW,  "_New Presentation", "<control>n", None, self.on_new_pres),
                ('open',    gtk.STOCK_OPEN, "_Open Presentation", "<control>o",   None, self.on_open_pres),
                ('save',    gtk.STOCK_SAVE, "_Save",        "<control>s",   None, self.on_save),
                ('save-as',  gtk.STOCK_SAVE_AS, "Save _As",  "<control><shift>s", None, self.save_as),
                ('quit',    gtk.STOCK_QUIT, None,           "<control>w",   None, self.on_quit),
                
                ('compile', None,       "_Compile"),
                ('compile-page',    gtk.STOCK_CONVERT, "Compile Page", "<shift>Return", "Compile Page", self.on_compile_page),
                ('compile-all',     gtk.STOCK_EXECUTE, "Compile Document", "<control><shift>Return", "Compile Document", self.on_compile_all),
                
                ('slide',  None,   "_Slide"),
                ('new-slide-menu', gtk.STOCK_NEW,     "_New Slide",       "", None, None),
                ('new-slide-toolbar', gtk.STOCK_NEW,  "_New Slide",       "", None, self.on_new_slide_toolbar),
                ('delete-slide', gtk.STOCK_DELETE,    "_Delete Slide",    "<shift>Delete", None, self.on_delete_slide),
                ('next-slide',  gtk.STOCK_GO_FORWARD, "Next Slide",       "Page_Down",     None, self.on_next_slide),
                ('prev-slide',  gtk.STOCK_GO_BACK,    "Previous Slide",   "Page_Up",       None, self.on_prev_slide),
        ])
        
        #action = action_group.get_action('new')
        #action.connect_proxy(newbutton)
        
        ui_manager = gtk.UIManager()
        ui_manager.insert_action_group(action_group)
        ui_manager.add_ui_from_string(UI_STRING)
        ui_manager.ensure_update()
        self._accel_group = ui_manager.get_accel_group()
        self.window.add_accel_group(self._accel_group)
        slidebar = ui_manager.get_widget("/SlideBar")
        slidebar.set_orientation(gtk.ORIENTATION_VERTICAL)
        slidebar.set_style(gtk.TOOLBAR_ICONS)
        slidebar.set_property('icon-size', gtk.ICON_SIZE_BUTTON) #MENU)
        self.skel_menu = gtk.Menu()
        ui_manager.get_widget("/TopMenu/Slide/NewSlide").set_submenu(self.skel_menu)
        return ui_manager.get_widget("/TopMenu"), ui_manager.get_widget("/ToolBar"), slidebar
    
    def generate_skeleton_menu(self):
        for item in self.skel_menu.get_children():
            self.skel_menu.remove(item)
        
        first = True
        for key, val in self.settings.skeletons.items():
            menuitem = gtk.MenuItem(key)
            menuitem.connect('activate', self.on_new_slide, val)
            menuitem.show()
            self.skel_menu.append(menuitem)
            if first:
                key, mod = gtk.accelerator_parse("<shift>Insert")
                menuitem.add_accelerator('activate', self._accel_group, key, mod, gtk.ACCEL_VISIBLE)
                first = False
    
    def on_window_delete(self, widget, event):
        if self.modified:
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
                try:
                    self.save()
                except ObstinateUserError:
                    return True
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
    
    def save_as(self, action=None):
        dialog = gtk.FileChooserDialog("Save As...", self.window, gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.fullfilename = dialog.get_filename()
            self.modified = True  # To update window title
            self.save()
        dialog.destroy()
    
    def on_view_slide(self, widget):
        if widget.get_active():
            selection = self.slidelist_view.get_selected_items()
            if selection:
                currslide, = self.pages.get(self.pages.get_iter(selection[0]), 0)
                self.viewer.load_doc(currslide.doc)
            else:  # In odd cases, there can be a document, but no slides.
                self.viewer.load_doc(None)
    
    def on_view_presentation(self, widget):
        if widget.get_active():
            self.viewer.load_doc(self.doc)
    
    def on_selection_changed(self, view):
        selection = self.slidelist_view.get_selected_items()
        if len(selection) == 0 and self.prev_selection and len(self.pages):
            if self.prev_selection[0] >= len(self.pages):
                self.prev_selection = (len(self.pages) - 1,)
            self.slidelist_view.select_path(self.prev_selection)
        elif len(selection) == 1:
            # Changing the buffer removes any selection, so we copy the
            # primary selection, if it exists.
            oldbuffer = self.currslide_view.get_buffer()
            if oldbuffer.get_has_selection():
                oldbuffer.add_selection_clipboard(gtk.clipboard_get("PRIMARY"))
            
            currslide, = self.pages.get(self.pages.get_iter(selection[0]), 0)
            self.currslide_view.set_buffer(currslide.buffer)
            self.currslide_view.set_sensitive(True)
            self.prev_selection = selection[0]
            if self.view_slide_button.get_active():
                self.viewer.load_doc(currslide.doc)
        else:
            self.currslide_view.set_sensitive(False)
            if len(self.pages) == 0 and self.view_slide_button.get_active():
                self.viewer.load_doc(None)
    
    # Right now, these two are used by drag-and-drop reordering
    def on_row_inserted(self, model, path, iter):
        self.prev_selection = path
        if self._loaded:
            self.modified = True
    
    def on_row_deleted(self, model, path):
        if path[0] < self.prev_selection[0]:
            self.prev_selection = (self.prev_selection[0] - 1,)
        if self._loaded:
            self.modified = True
    
    def on_rows_reordered(self, model, path, iter, new_order):
        self.modified = True
    
    def on_new_slide_toolbar(self, action):
        self.skel_menu.popup(None, None, None, 1, gtk.get_current_event_time())
    
    def on_new_slide(self, action, content=""):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[0]
            iter = self.pages.get_iter(selection)
        else:
            iter = None
        self.add_page(content, after=iter)
        self.slidelist_view.unselect_all()
        if selection:
            self.slidelist_view.select_path((selection[0]+1,))
        else:
            self.slidelist_view.select_path((0,))
        # Switch to slide editor and focus
        self.notebook.set_current_page(1)
        self.currslide_view.grab_focus()
    
    def on_delete_slide(self, action):
        for selection in self.slidelist_view.get_selected_items():
            iter = self.pages.get_iter(selection)
            self.delete_page(iter)
    
    # http://www.pygtk.org/pygtk2tutorial/sec-TreeViewDragAndDrop.html
    def on_drag_data_get(self, iconview, context, selection_data, target_id, etime):
        if target_id == self.SAME_WIDGET and context.action == gtk.gdk.ACTION_MOVE:
            self.drag_get_reorder(selection_data)
        else:
            self.drag_get_create(selection_data)
    
    def on_drag_data_received(self, iconview, context, x, y, selection_data, target_id, etime):
        drop_info = self.slidelist_view.get_dest_item_at_pos(x, y)
        if target_id == self.SAME_WIDGET and context.action == gtk.gdk.ACTION_MOVE:
            self.drag_received_reorder(context, drop_info, selection_data, etime)
        else:
            self.drag_received_create(context, drop_info, selection_data, etime)
    
    def drag_get_reorder(self, selection_data):
        data = repr(self.slidelist_view.get_selected_items())
        selection_data.set(selection_data.target, 8, data)
    
    def drag_received_reorder(self, context, drop_info, selection_data, etime):
        data = eval(selection_data.data) # [(a,), (b,) ...
        data = [d[0] for d in data]      # [a, b, ...
        data.sort()
        
        if drop_info:
            path, position = drop_info
            index = path[0]
            if position not in (gtk.ICON_VIEW_DROP_LEFT, gtk.ICON_VIEW_DROP_ABOVE):
                index += 1
        else:
            index = len(self.pages)
        
        index0 = index
        order = range(len(self.pages))
        for d in data:
            order.remove(d)
            if d < index0:
                index -= 1
        assert(index >= 0)
        self.pages.reorder(order[:index] + data + order[index:])
    
    def drag_get_create(self, selection_data):
        data = []
        # Note that this puts the slides in reverse order.
        for selection in self.slidelist_view.get_selected_items():
            slide, = self.pages.get(self.pages.get_iter(selection), 0)
            data.append(slide.get_content())
        selection_data.set(selection_data.target, 8, SEP.join(data))
    
    def drag_received_create(self, context, drop_info, selection_data, etime):
        data = selection_data.data.split(SEP)
        self.prev_selection = None  # Disable unselect preventer
        self.slidelist_view.unselect_all()
        if drop_info:
            path, position = drop_info
            iter = self.pages.get_iter(path)
            if position in (gtk.ICON_VIEW_DROP_LEFT, gtk.ICON_VIEW_DROP_ABOVE):
                data.reverse()  # Put in forward order, since we'll insert them all
                newpath = path  # before the same element.
                for d in data:
                    self.add_page(d, before=iter, render=True)
                    self.slidelist_view.select_path(newpath)
                    newpath = (newpath[0] + 1,)
                # Scroll to the right if needed.  (The left will be where we dropped it,
                # and therefore already in view
                self.slidelist_view.scroll_to_path((newpath[0] - 1,), False, 0, 0)
            else:
                newpath = (path[0] + 1,)
                # We want the data in reverse order, since we'll be inserting them
                # all after the same element.
                for d in data:
                    self.add_page(d, after=iter, render=True)
                    self.slidelist_view.select_path(newpath)
                self.slidelist_view.scroll_to_path((path[0] + len(data),), False, 0, 0)
        else:
            for d in data:
                self.add_page(d, render=True)
                self.slidelist_view.select_path((len(self.pages) - 1,))
            self.slidelist_view.scroll_to_path((len(self.pages)-1,), False, 0, 0)
        
        # Run on_selection_changed when we're done rendering all the new pages, so
        # we can load the current document into the viewer.  This doesn't work if
        # we have multiple pages chosen, but the page view is sorta odd in that
        # case, regardless.
        self.executor.add_callback(self.on_selection_changed)
        
        if context.action == gtk.gdk.ACTION_MOVE:
            context.finish(True, True, etime)
    
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
        self.compile(lambda status: not status and self.view_presentation_button.clicked())
    
    
    def on_next_slide(self, action):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[0][0]
            if selection < len(self.pages)-1:
                self.prev_selection = None
                self.slidelist_view.unselect_all()
                self.slidelist_view.select_path((selection+1,))
                self.slidelist_view.scroll_to_path((selection+1,), False, 0, 0)
    
    def on_prev_slide(self, action):
        selection = self.slidelist_view.get_selected_items()
        if selection:
            selection = selection[-1][0]
            if selection > 0:
                self.prev_selection = None
                self.slidelist_view.unselect_all()
                self.slidelist_view.select_path((selection-1,))
                self.slidelist_view.scroll_to_path((selection-1,), False, 0, 0)
    
    def on_new_pres(self, action):
        LatexDocument()
    
    def on_open_pres(self, action):
        dialog = gtk.FileChooserDialog("Open...", self.window, gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            if not self._filename and not self.modified:
                glib.idle_add(self.load, filename)
            else:
                glib.idle_add(lambda: LatexDocument(filename) and False)
        dialog.destroy()
