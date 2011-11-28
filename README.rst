SlideDeX
========

SlideDeX is an editor for LaTeX presentations.  Using Beamer_,
Prosper_, or even the *slides* class, it's possible to make beautiful
slides for your presentation.  As the presentation grows, working with
it becomes more difficult.  Compilation takes longer as the number of
slides increases, slowing the tweak-and-test cycle.  It can become
harder to find the source corresponding to a specific slide.

.. _Beamer: https://bitbucket.org/rivanvx/beamer/wiki/Home
.. _Prosper: http://www.ctan.org/tex-archive/macros/latex/contrib/prosper

SlideDeX attempts to solve these problems by splitting the presentation
into its individual slides.  Each can be edited and compiled
individually, and the source of a given slide is readily available.  To
do this, SlideDeX relies on the fact that, unlike many types of LaTeX
documents, presentations have pages which are largely independent of
each other.  Thus, the original LaTeX file may be split into a header,
a footer, and a set of individual slides.  Each slide may be assembled
into a document with the header and footer and then compiled quickly.
Only when all slides are ready does the entire presentation need to be
compiled together.

SlideDeX is currently very much pre-alpha software — use at your own
risk!  The author finds it usable, but there are many missing features.
Although it hasn't caused any data loss for me, I can't promise that
you'll be so lucky.  Back up your presentations before using SlideDeX!

Requirements
------------
SlideDeX is written in Python 2.  It should work with any 2.6 or 2.7
version, though that has not been carefully tested.  SlideDeX uses
pyGTK and Glade.  Linux systems probably have these installed; Mac and
Windows people may be in for an adventure.  (If you get it working,
please let us know how!)

The Poppler_ library and its `Python bindings`_ are used for displaying
the slides.  The former is probably installed on your Linux system; the
latter may not be.  In Debian-based systems, install the
``python-poppler`` package.  Again, good luck to you Mac and Windows
users.

.. _Poppler: http://poppler.freedesktop.org/
.. _Python bindings: https://launchpad.net/poppler-python

Of course, you also need a working TeX installation somewhere on your
path.

Installation
------------
The best way to get SlideDeX is by cloning the git repository::

  git clone git://github.com/rschroll/slidedex.git

Alternatively, you can download and unpack the tarball_.

.. _tarball: https://github.com/rschroll/slidedex/tarball/master

Currently, SlideDeX has no installation procedure.  Instead, run the
script from wherever you downloaded it::

  /path/to/install/slidedex/bin/slidex <filename>

Usage
-----
Unfortunately, SlideDeX does not currently import existing
presentations.  You must either create them from an empty presentation
or edit an existing presentation to be in the form that SlideDeX
expects.  Specifically, you need to add a separator ::

  %%SLIDEEDIT%%

after the header, before the footer, and in between all slides.

Before compiling the presentation, in whole or in part, it must have a
filename chosen.  SlideDeX will prompt you for the name at an
appropriate place.  If you do not provide a name, SlideDeX will
complain about you in a passive-aggressive manner.  Whether this is a
bug or a feature has not been decided.

The compilation process is currently hardcoded in the ``_do_latex``
method of ``LatexDocument`` to be ::

  latex -halt-on-error <basename>
  dvips <basename>
  ps2pdf <basename>.ps

If you want to change that, change the first argument of
``self.executor.add()`` in that method.  Hopefully this will become
more configurable soon.

Development
-----------
SlideDeX is being developed on GitHub_.  Check out that site for
updated versions.  Please report bugs and feature requests to the
Github `bug tracker`_.

.. _GitHub: https://github.com/rschroll/slidedex
.. _bug tracker: https://github.com/rschroll/slidedex/issues

SlideDeX has been written (thus far) by Robert Schroll
(rschroll@gmail.com).  Feel free to get in touch with questions and
comments.
