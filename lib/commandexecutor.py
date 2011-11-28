# Copyright 2010, 2011 Robert Schroll
#
# This file is part of SlideDeX and is distributed under the terms of
# the BSD license.  See the file COPYING for full details.
#
######################################################################

import gtk
import vte


class CommandExecutor(object):
    def __init__(self, parent):
        self.is_running = False
        self.command_queue = []
        self.parent = parent
        
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
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.set_resizable(False)
        self.window.set_transient_for(self.parent.window)
    
    @property
    def dir(self):
        return self.parent.dir
    
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
            pid = self.term.fork_command(command[0], command, directory=self.dir)
    
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
