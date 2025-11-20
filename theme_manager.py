# theme_manager.py
import tkinter as tk
from tkinter import ttk

class ThemeManager:
    """Manages all color schemes and ttk styles"""
    
    def __init__(self, root):
        self.root = root
        
        # Colors
        self.BG_DARK = "#1e1e1e"
        self.BG_DARKER = "#121212"
        self.FG_LIGHT = "#e0e0e0"
        self.FG_DIM = "#a0a0a0"
        self.ACCENT_GREEN = "#00C853"
        self.ACCENT_DARK = "#005020"
        self.ERROR_RED = "#ff5252"
        self.WARNING_ORANGE = "#FFAB40"
        
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply all ttk styles"""
        self.root.configure(bg=self.BG_DARK)
        
        s = ttk.Style()
        s.theme_use('clam')

        # Global defaults
        s.configure(".", background=self.BG_DARK, foreground=self.FG_LIGHT, 
                    font=("Helvetica", 10), focuscolor=self.BG_DARK)
        
        # Specific Widget Styles
        s.configure("TFrame", background=self.BG_DARK)
        s.configure("TPanedwindow", background=self.BG_DARK)
        s.configure("TLabel", background=self.BG_DARK, foreground=self.FG_LIGHT)
        s.configure("TButton", background=self.BG_DARKER, foreground=self.ACCENT_GREEN, 
                    borderwidth=1, focuscolor=self.ACCENT_GREEN, bordercolor=self.ACCENT_DARK)
        s.map("TButton", background=[('active', self.ACCENT_DARK), ('pressed', self.ACCENT_GREEN)],
                        foreground=[('pressed', self.BG_DARKER)])
        
        # Disabled Button Style
        s.configure("DisabledRed.TButton", background=self.BG_DARKER, foreground=self.ERROR_RED, 
                    borderwidth=1, bordercolor=self.ACCENT_DARK)
        s.map("DisabledRed.TButton", 
            foreground=[('disabled', self.ERROR_RED)],
            background=[('disabled', self.BG_DARKER)],
            bordercolor=[('disabled', self.ACCENT_DARK)])
        
        s.configure("TButton", focuscolor=self.BG_DARKER)

        s.configure("TEntry", fieldbackground=self.BG_DARKER, foreground=self.ACCENT_GREEN, 
                    bordercolor=self.BG_DARK, borderwidth=2, insertcolor=self.ACCENT_GREEN) 
        s.map("TEntry", 
            fieldbackground=[('active', self.BG_DARKER), ('!disabled', self.BG_DARKER)],
            foreground=[('disabled', self.ERROR_RED)],
            bordercolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)],
            lightcolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)],
            darkcolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)])
        
        # Combobox
        s.configure("TCombobox", fieldbackground=self.BG_DARKER, foreground=self.ACCENT_GREEN,
                    background=self.BG_DARK, arrowcolor=self.ACCENT_GREEN, bordercolor=self.ACCENT_DARK,
                    darkcolor=self.ACCENT_DARK, lightcolor=self.BG_DARK, selectbackground=self.BG_DARKER,
                    selectforeground=self.ACCENT_GREEN)
        s.map("TCombobox",
            fieldbackground=[('readonly', self.BG_DARKER), ('disabled', self.BG_DARK)],
            foreground=[('disabled', self.ERROR_RED), ('readonly', self.ACCENT_GREEN)],
            background=[('readonly', self.BG_DARK), ('disabled', self.BG_DARK)],
            selectbackground=[('readonly', self.BG_DARKER)],
            selectforeground=[('readonly', self.ACCENT_GREEN)],
            bordercolor=[('focus', self.ACCENT_GREEN)],
            darkcolor=[('focus', self.ACCENT_GREEN)],
            arrowcolor=[('disabled', self.FG_DIM)])
        
        self.root.option_add('*TCombobox*Listbox.background', self.BG_DARKER)
        self.root.option_add('*TCombobox*Listbox.foreground', self.FG_LIGHT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.ACCENT_DARK)
        self.root.option_add('*TCombobox*Listbox.selectForeground', self.FG_LIGHT)

        # Checkbutton
        s.configure("TCheckbutton", background=self.BG_DARK, foreground=self.FG_LIGHT, 
                    indicatorcolor=self.BG_DARKER, indicatorrelief='flat')
        s.map("TCheckbutton", 
            indicatorcolor=[('selected', self.ACCENT_GREEN), ('pressed', self.ACCENT_GREEN), 
                          ('active', self.ACCENT_DARK)],
            background=[('active', self.BG_DARK)],
            foreground=[('disabled', self.ERROR_RED), ('selected', self.ACCENT_GREEN), 
                       ('active', self.ACCENT_GREEN)])

        s.configure("TLabelframe", background=self.BG_DARK, foreground=self.ACCENT_GREEN, 
                    bordercolor=self.ACCENT_DARK)
        s.configure("TLabelframe.Label", background=self.BG_DARK, foreground=self.ACCENT_GREEN)
        
        s.configure("Treeview", background=self.BG_DARKER, foreground=self.FG_LIGHT, 
                    fieldbackground=self.BG_DARKER, borderwidth=0)
        s.map("Treeview", background=[('selected', self.ACCENT_DARK)], 
                        foreground=[('selected', self.FG_LIGHT)])
        s.configure("Treeview.Heading", background=self.BG_DARK, foreground=self.FG_DIM, relief="flat")

        s.configure("TSeparator", background=self.BG_DARKER)
        s.configure("Vertical.TScrollbar", background=self.BG_DARK, troughcolor=self.BG_DARKER, 
                    bordercolor=self.BG_DARK, arrowcolor=self.ACCENT_GREEN)
        
        s.configure("Invalid.TEntry", 
                fieldbackground=self.BG_DARKER, 
                foreground=self.ERROR_RED,
                bordercolor=self.ERROR_RED,
                borderwidth=2,
                insertcolor=self.ERROR_RED)
        s.map("Invalid.TEntry",
            bordercolor=[('focus', self.ERROR_RED), ('!focus', self.ERROR_RED)],
            lightcolor=[('focus', self.ERROR_RED), ('!focus', self.ERROR_RED)],
            darkcolor=[('focus', self.ERROR_RED), ('!focus', self.ERROR_RED)])

        # Custom Named Styles
        s.configure("Title.TLabel", font=("Helvetica", 14, "bold"), foreground=self.ACCENT_GREEN)
        s.configure("Section.TLabel", font=("Helvetica", 10, "bold"), foreground=self.ACCENT_GREEN)
        s.configure("Tooltip.TLabel", foreground=self.FG_DIM, font=("Helvetica", 8, "italic"))
        s.configure("Description.TLabel", font=("Helvetica", 10), foreground=self.FG_LIGHT)
        s.configure("Example.TLabel", font=("Courier", 9), foreground=self.ACCENT_GREEN)
        s.configure("Sudo.TCheckbutton", font=("Helvetica", 9, "bold"))
        s.map("Sudo.TCheckbutton", foreground=[('!disabled', self.ERROR_RED), ('disabled', self.FG_DIM)])
    
    def get_theme_config(self):
        """Returns dict of colors for other modules"""
        return {
            "BG_DARK": self.BG_DARK,
            "BG_DARKER": self.BG_DARKER,
            "FG_LIGHT": self.FG_LIGHT,
            "FG_DIM": self.FG_DIM,
            "ACCENT_GREEN": self.ACCENT_GREEN,
            "ACCENT_DARK": self.ACCENT_DARK,
            "ERROR_RED": self.ERROR_RED
        }