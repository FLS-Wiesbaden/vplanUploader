# -*- coding: utf-8 -*-
# Creates a task-bar icon with balloon tip.  Run from Python.exe to see the
# messages printed.  Right click for balloon tip.  Double click to exit.
# original version of this demo available at http://www.itamarst.org/software/
import win32api, win32con, win32gui, win32gui_struct, os, time
import collections

class Taskbar:
    par = None
    FIRST_ID = 1023

    def __init__(self, par, menu_options):
        self.par = par
        self.visible = 0
        # MENU
        self._next_action_id = self.FIRST_ID
        self.menu_actions_by_id = set()
        self.menu_options = self._add_ids_to_menu_options(list(menu_options))
        self.menu_actions_by_id = dict(self.menu_actions_by_id)
        del self._next_action_id


        message_map = {
            win32con.WM_DESTROY: self.onDestroy,
            win32con.WM_USER+20 : self.onTaskbarNotify,
            win32con.WM_COMMAND: self.command,
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
    
    def _add_ids_to_menu_options(self, menu_options):
        result = []
        for menu_option in menu_options:
            option_text, option_icon, option_action = menu_option
            if isinstance(option_action, collections.Callable) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.add((self._next_action_id, option_action))
                result.append(menu_option + (self._next_action_id,))
            elif non_string_iterable(option_action):
                result.append((option_text,
                               option_icon,
                               self._add_ids_to_menu_options(option_action),
                               self._next_action_id))
            else:
                print('Unknown item', option_text, option_icon, option_action)
            self._next_action_id += 1
        return result

    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options)
        #win32gui.SetMenuDefaultItem(menu, 1000, 0)
        
        pos = win32gui.GetCursorPos()
        # See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu,
                                win32con.TPM_LEFTALIGN,
                                pos[0],
                                pos[1],
                                0,
                                self.hwnd,
                                None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
    
    def create_menu(self, menu, menu_options):
        for option_text, option_icon, option_action, option_id in menu_options[::-1]:
            if option_icon:
                option_icon = self.prep_menu_icon(option_icon)
            
            if option_id in self.menu_actions_by_id:                
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                wID=option_id)
                win32gui.InsertMenuItem(menu, 0, 1, item)
            else:
                submenu = win32gui.CreatePopupMenu()
                self.create_menu(submenu, option_action)
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                hSubMenu=submenu)
                win32gui.InsertMenuItem(menu, 0, 1, item)

    def prep_menu_icon(self, icon):
        # First load the icon.
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
        hicon = win32gui.LoadImage(0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)

        hdcBitmap = win32gui.CreateCompatibleDC(0)
        hdcScreen = win32gui.GetDC(0)
        hbm = win32gui.CreateCompatibleBitmap(hdcScreen, ico_x, ico_y)
        hbmOld = win32gui.SelectObject(hdcBitmap, hbm)
        # Fill the background.
        brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
        win32gui.FillRect(hdcBitmap, (0, 0, 16, 16), brush)
        # unclear if brush needs to be feed.  Best clue I can find is:
        # "GetSysColorBrush returns a cached brush instead of allocating a new
        # one." - implies no DeleteObject
        # draw the icon
        win32gui.DrawIconEx(hdcBitmap, 0, 0, hicon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL)
        win32gui.SelectObject(hdcBitmap, hbmOld)
        win32gui.DeleteDC(hdcBitmap)
        
        return hbm

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        self.execute_menu_option(id)
        
    def execute_menu_option(self, id):
        menu_action = self.menu_actions_by_id[id]      
        menu_action()        

    def show(self):
        """Display the taskbar icon"""
        print('Im here and will show me now!')
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
        print('someone doesnt like me :-(')
        if self.visible:
            nid = (self.hwnd, 0)
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        self.visible = 0
        
    def onDestroy(self, hwnd, msg, wparam, lparam):
        print("someone wants to destroy me!")
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
        self.show_menu()
        #pass

class DemoTaskbar(Taskbar):
    icon = None
    hicon = None
    par = None

    def __init__(self, par, logo, title, menu):
        Taskbar.__init__(self, par, menu)
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
            print('Cant find icon file - using default.')
            self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    def onClick(self):
        print('you clicked - now i will call getNewFiles')
        self.par.getNewFiles()

    def onDoubleClick(self):
        print("you double clicked, bye!")
        self.par.bye()
        win32gui.PostQuitMessage(0)

    #def onRightClick(self):
    def showInfo(self, title, msg):
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_INFO
        nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon, "", msg, 10, title, win32gui.NIF_MESSAGE)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
            

def non_string_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return not isinstance(obj, str)
