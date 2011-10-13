import gtk
import poppler
from misc import render_to_pixbuf


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
