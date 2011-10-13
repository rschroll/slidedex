import os
import gtk
import poppler
from commandexecutor import executor

SEP = "\n%%SLIDEEDIT%%\n"

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

def render_to_pixbuf(page, msize):
    psize = page.get_size() # floats
    scale = min([s/ps for s, ps in zip(msize, psize)])
    size = [int(ps*scale) for ps in psize]
    pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, *size)
    page.render_to_pixbuf(0,0,size[0],size[1],scale,0,pb)
    return pb
