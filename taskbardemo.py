# -*- coding: utf-8 -*-
# Creates a task-bar icon with balloon tip.  Run from Python.exe to see the
# messages printed.  Right click for balloon tip.  Double click to exit.
# original version of this demo available at http://www.itamarst.org/software/
import win32api, win32con, win32gui, os, time

class Taskbar:
    par = None
    
    def __init__(self, par):
	self.par = par
        self.visible = 0
        message_map = {
            win32con.WM_DESTROY: self.onDestroy,
            win32con.WM_USER+20 : self.onTaskbarNotify,
        }
        # Register the Window class.
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "Vertretungsplaner"
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        wc.hCursor = win32gui.LoadCursor( 0, win32con.IDC_ARROW )
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = message_map # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(wc)
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow( classAtom, "FLS Vertretungsplaner", style, \
                    0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT, \
                    0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)

    def setIcon(self, hicon, tooltip=None):
        self.hicon = hicon
        self.tooltip = tooltip
        
    def show(self):
        """Display the taskbar icon"""
	print 'Im here and will show me now!'
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE
        if self.tooltip is not None:
            flags |= win32gui.NIF_TIP
            nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon, self.tooltip)
        else:
            nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon)
        if self.visible:
            self.hide()
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        self.visible = 1

    def hide(self):
        """Hide the taskbar icon"""
	print 'someone doesnt like me :-('
        if self.visible:
            nid = (self.hwnd, 0)
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        self.visible = 0
        
    def onDestroy(self, hwnd, msg, wparam, lparam):
	print "someone wants to destroy me!"
	pass

    def onTaskbarNotify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP:
            self.onClick()
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            self.onDoubleClick()
        elif lparam ==  win32con.WM_RBUTTONUP:
            self.onRightClick()
        return 1

    def onClick(self):
        """Override in subclassess"""
        pass

    def onDoubleClick(self):
        """Override in subclassess"""
        pass
    def onRightClick(self):
        """Override in subclasses"""
        pass

class DemoTaskbar(Taskbar):
    icon = None
    hicon = None
    par = None

    def __init__(self, par, logo, title, menu):
        Taskbar.__init__(self, par)
	self.par = par
	self.refresh_icon(logo)
	self.setIcon(self.hicon)
        self.show()

    def sayGoodbye(self):
	self.hide()
	self.par.setRun(False)
	win32gui.PostQuitMessage(0)

    def onDestroy(self, hwnd, msg, wparam, lparam):
        self.hide()
	self.par.setRun(False)
        win32gui.PostQuitMessage(0) # Terminate the app.

    def refresh_icon(self, logo):
    	# Try and find a custom icon
        hinst = win32gui.GetModuleHandle(None)
	self.icon = logo
        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            self.hicon = win32gui.LoadImage(hinst, self.icon,win32con.IMAGE_ICON,0,0,icon_flags)
        else:
	    print "Can't find icon file - using default."
	    self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    def onClick(self):
        print 'you clicked - now i will call getNewFiles'
	self.par.getNewFiles()

    def onDoubleClick(self):
        print "you double clicked, bye!"
	self.par.bye(self.par)
        win32gui.PostQuitMessage(0)

    #def onRightClick(self):
    def showInfo(self, title, msg):
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_INFO
        nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon, "", msg, 10, title, win32gui.NIF_MESSAGE)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
            
