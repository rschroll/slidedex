# Copyright 2010, 2011 Robert Schroll
#
# This file is part of SlideDeX and is distributed under the terms of
# the BSD license.  See the file COPYING for full details.
#
######################################################################

import os
import gtk
import poppler

SEP = "\n%%SLIDEEDIT%%\n"

def render_to_pixbuf(page, msize):
    psize = page.get_size() # floats
    scale = min([s/ps for s, ps in zip(msize, psize)])
    size = [int(ps*scale) for ps in psize]
    pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, *size)
    page.render_to_pixbuf(0,0,size[0],size[1],scale,0,pb)
    return pb
