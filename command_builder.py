import json
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import pyperclip
from pathlib import Path
import webbrowser
import re
import datetime
import calendar
from PIL import Image, ImageTk
import os
import threading
import shlex

# --- Optional Modules (Graceful Degradation) ---
try:
    import ai_analyzer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("Warning: ai_analyzer.py not found. AI features disabled.")

try:
    import settings_panel
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    print("Warning: settings_panel.py not found. Settings features disabled.")
    
try:
    import update_manager
    UPDATE_MANAGER_AVAILABLE = True
except ImportError:
    UPDATE_MANAGER_AVAILABLE = False
    print("Warning: update_manager.py not found. Update features disabled.")


def get_resource_path(relative_path):
    """Get absolute path to BUNDLED resource (read-only)"""
    try:
        # PyInstaller extracts bundled files here
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent
    return base_path / relative_path

def get_data_dir():
    """Get persistent user data directory (writable)"""
    if getattr(sys, 'frozen', False):
        # Running as executable - use OS-specific location
        if sys.platform == 'win32':
            data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'LinuxCommander'
        elif sys.platform == 'darwin':
            data_dir = Path.home() / 'Library' / 'Application Support' / 'LinuxCommander'
        else:
            data_dir = Path.home() / '.local' / 'share' / 'LinuxCommander'
    else:
        # Running from source - use local directory
        data_dir = Path(__file__).parent
    
    return data_dir

# --- Constants ---
APP_DIR = get_resource_path(".")  # For bundled resources like logo
BUNDLED_COMMANDS_DIR = get_resource_path("commands")  # Read-only bundled commands
USER_COMMANDS_DIR = get_data_dir() / "commands"  # Writable user location
COMMANDS_DIR = USER_COMMANDS_DIR
WINDOW_GEOMETRY = "900x700"
logo_path = get_resource_path("LOGO.png")
APP_TITLE = "Linux Command Builder"

class CommandBuilderApp:
    
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        
        # --- Setup Theme First ---
        self._setup_theme()
        # ------------------------------
        
        # Trackers for our custom windows
        self.ai_result_window = None 
        self._current_msg = None

        # --- BIND CLICK ON MAIN WINDOW TO AUTO-CLOSE NOTIFICATIONS ---
        # 'add=+' ensures we don't overwrite other necessary bindings
        self.root.bind("<Button-1>", self._auto_close_msg, add="+")
        self.root.bind("<Button-1>", self._on_background_click, add="+")
        # ------------------------------------------------------------------

        # --- Dispatch Dictionaries ---
        self._widget_builders = {
            "permission_grid": self._build_permission_grid,
            "checkbox": self._build_widget_checkbox,
            "dropdown": self._build_widget_dropdown,
            "size_input": self._build_widget_size_input,
            "relative_time_input": self._build_widget_relative_time_input,
            "notable_text_input": self._build_widget_notable_text_input,
            "permission_input": self._build_widget_permission_input,
            "date_input": self._build_widget_date_input,
            "url": self._build_widget_url,
            "file_w_ext": self._build_widget_file_w_ext,
            "text": self._build_widget_text,
            "file_picker": self._build_widget_file_picker,
            "dir_picker": self._build_widget_dir_picker,
            "file_save_as": self._build_widget_file_save_as,
            "number_input": self._build_widget_number_input
        }

        self._widget_clearers = {
            "checkbox": self._clear_widget_checkbox,
            "size_input": self._clear_widget_size_input,
            "relative_time_input": self._clear_widget_relative_time_input,
            "notable_text_input": self._clear_widget_notable_text_input,
            "permission_input": self._clear_widget_permission_input,
            "date_input": self._clear_widget_date_input,
            "url": self._clear_widget_url,
            "file_w_ext": self._clear_widget_file_w_ext,
            "text": self._clear_widget_text,
            "dropdown": self._clear_widget_text,
            "permission_grid": lambda item: None,
            "file_picker": self._clear_widget_text,
            "dir_picker": self._clear_widget_text,
            "file_save_as": self._clear_widget_text,
            "number_input": self._clear_widget_text
        }

        self._widget_arg_getters = {
            "checkbox": self._get_arg_from_checkbox,
            "size_input": self._get_arg_from_size_input,
            "relative_time_input": self._get_arg_from_relative_time_input,
            "notable_text_input": self._get_arg_from_notable_text_input,
            "permission_input": self._get_arg_from_permission_input,
            "date_input": self._get_arg_from_date_input,
            "url": self._get_arg_from_url,
            "file_w_ext": self._get_arg_from_file_w_ext,
            "text": self._get_arg_from_text,
            "dropdown": self._get_arg_from_text,
            "permission_grid": lambda item, cmd_name: None,
            "file_picker": self._get_arg_from_text,
            "dir_picker": self._get_arg_from_text,
            "file_save_as": self._get_arg_from_text,
            "number_input": self._get_arg_from_text
        }

        self._widget_active_checkers = {
            "checkbox": self._is_active_checkbox,
            "size_input": self._is_active_num_var,
            "relative_time_input": self._is_active_num_var,
            "notable_text_input": self._is_active_var,
            "permission_input": self._is_active_var,
            "date_input": self._is_active_date_input,
            "url": self._is_active_url,
            "file_w_ext": self._is_active_file_w_ext,
            "text": self._is_active_var,
            "dropdown": self._is_active_var,
            "permission_grid": lambda item: False,
            "file_picker": self._is_active_var,
            "dir_picker": self._is_active_var,
            "file_save_as": self._is_active_var,
            "number_input": self._is_active_var
        }
        # --- End Dispatch Dictionaries ---
        
        # --- COMMAND LOADING ---
        self.COMMANDS_DATA = {}

        # Initialize update manager BEFORE loading commands
        self.update_manager = None
        if UPDATE_MANAGER_AVAILABLE:
            theme_config = {
                "BG_DARK": self.BG_DARK,
                "BG_DARKER": self.BG_DARKER,
                "FG_LIGHT": self.FG_LIGHT,
                "FG_DIM": self.FG_DIM,
                "ACCENT_GREEN": self.ACCENT_GREEN,
                "ACCENT_DARK": self.ACCENT_DARK,
                "ERROR_RED": self.ERROR_RED
            }
            self.update_manager = update_manager.UpdateManager(
                self.root,
                COMMANDS_DIR,
                theme_config,
                on_update_complete=self.reload_commands
            )

        # --- Initialize widget tracking variables ---
        self.widget_vars = []
        self.current_command_info = {}
        self.permission_vars = {}
        self.sudo_var = tk.BooleanVar()

        # --- BUILD THE UI (THIS WAS MISSING!) ---
        self._setup_main_ui()
        
        # Load commands from disk
        self._load_commands()
        
        # --- POPULATE THE COMMAND TREE (THIS WAS MISSING!) ---
        self._populate_command_tree()

    # --- COMMAND LOADING METHOD ---
    def _load_commands(self):
        """Load commands from disk - no auto-download."""
        # Try user directory first, then bundled
        bundled_dir = get_resource_path("commands")
        
        if COMMANDS_DIR.exists() and any(COMMANDS_DIR.glob("*.json")):
            load_from = COMMANDS_DIR
        elif bundled_dir.exists() and any(bundled_dir.glob("*.json")):
            load_from = bundled_dir
        else:
            # No commands found - first run scenario
            if UPDATE_MANAGER_AVAILABLE:
                msg = ("No command files found.\n\n"
                    "This appears to be your first run.\n"
                    "Would you like to download command files now?")
                if messagebox.askyesno("First Run Setup", msg):
                    self.root.after(100, self.open_update_manager)
            else:
                messagebox.showerror("Setup Required", 
                    "No command files found and Update Manager is unavailable.\n\n"
                    "Please manually download the 'commands' folder from:\n"
                    "https://github.com/crenta/Linux-Commander")
            return
        
        # Load all JSON files
        load_errors = []
        for json_file in load_from.glob("*.json"):
            if json_file.name.startswith("."):  # Skip hidden files like .local_hashes.json
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    self.COMMANDS_DATA.update(json.load(f))
            except json.JSONDecodeError as e:
                load_errors.append(f"{json_file.name}: Invalid JSON at line {e.lineno}")
            except Exception as e:
                load_errors.append(f"{json_file.name}: {str(e)}")
        
        # Handle corrupted files
        if load_errors:
            error_summary = "\n".join(load_errors[:4])
            if len(load_errors) > 4:
                error_summary += f"\n...and {len(load_errors) - 4} more."
            
            if UPDATE_MANAGER_AVAILABLE:
                msg = (f"Some command files failed to load:\n\n{error_summary}\n\n"
                    "Would you like to re-download these files?")
                if messagebox.askyesno("Loading Errors", msg):
                    self.root.after(100, self.open_update_manager)
            else:
                messagebox.showerror("Loading Errors", 
                    f"Some files are corrupted:\n\n{error_summary}")
        
        # Final check
        if not self.COMMANDS_DATA:
            messagebox.showerror("Fatal Error", 
                "No valid command files could be loaded.\n\n"
                "Please use the Update Manager to download fresh files.")

    # edit
    def reload_commands(self):
        """Reload commands after update - called by update manager."""
        self.COMMANDS_DATA.clear()
        self._load_commands()
        
        # Refresh the command tree
        for item in self.command_tree.get_children():
            self.command_tree.delete(item)
        self._populate_command_tree()
        
        # Show success message
        self._show_styled_message("Success", 
            f"Commands reloaded successfully!\n\n"
            f"Total commands available: {len(self.COMMANDS_DATA)}")



    # --- METHOD: Centralized Theme Setup ---
    def _setup_theme(self):
        """Defines colors and configures ttk styles for a hacker aesthetic."""
        self.BG_DARK = "#1e1e1e"
        self.BG_DARKER = "#121212"
        self.FG_LIGHT = "#e0e0e0"
        self.FG_DIM = "#a0a0a0"
        self.ACCENT_GREEN = "#00C853"
        self.ACCENT_DARK = "#005020"
        self.ERROR_RED = "#ff5252"
        self.WARNING_ORANGE = "#FFAB40" # not used

        self.root.configure(bg=self.BG_DARK)

        s = ttk.Style()
        s.theme_use('clam')

        # Global defaults
        s.configure(".", background=self.BG_DARK, foreground=self.FG_LIGHT, font=("Helvetica", 10), focuscolor=self.BG_DARK)
        
        # Specific Widget Styles
        s.configure("TFrame", background=self.BG_DARK)
        s.configure("TPanedwindow", background=self.BG_DARK)
        s.configure("TLabel", background=self.BG_DARK, foreground=self.FG_LIGHT)
        s.configure("TButton", background=self.BG_DARKER, foreground=self.ACCENT_GREEN, 
                    borderwidth=1, focuscolor=self.ACCENT_GREEN, bordercolor=self.ACCENT_DARK)
        s.map("TButton", background=[('active', self.ACCENT_DARK), ('pressed', self.ACCENT_GREEN)],
                         foreground=[('pressed', self.BG_DARKER)])
        
        # Disabled Button Style
        s.configure("DisabledRed.TButton", background=self.BG_DARKER, foreground=self.ERROR_RED, borderwidth=1, bordercolor=self.ACCENT_DARK)
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
              # The 'disabled' state must come BEFORE '!focus' so it takes priority
              bordercolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)],
              lightcolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)],
              darkcolor=[('disabled', self.ERROR_RED), ('focus', self.ACCENT_GREEN), ('!focus', self.BG_DARK)])
        
        # Combobox with restored button border
        s.configure("TCombobox", fieldbackground=self.BG_DARKER, foreground=self.ACCENT_GREEN,
                    background=self.BG_DARK, arrowcolor=self.ACCENT_GREEN, bordercolor=self.ACCENT_DARK,
                    darkcolor=self.ACCENT_DARK, lightcolor=self.BG_DARK, selectbackground=self.BG_DARKER,
                    selectforeground=self.ACCENT_GREEN)
        s.map("TCombobox",
              fieldbackground=[('readonly', self.BG_DARKER), ('disabled', self.BG_DARK)],
              foreground=[('disabled', self.ERROR_RED),       # <-- ADD THIS for disabled dropdowns
                          ('readonly', self.ACCENT_GREEN)],
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

        # --- Checkbutton Mapping for Green/Orange text ---
        s.configure("TCheckbutton", background=self.BG_DARK, foreground=self.FG_LIGHT, 
                    indicatorcolor=self.BG_DARKER, indicatorrelief='flat')
        s.map("TCheckbutton", 
              indicatorcolor=[('selected', self.ACCENT_GREEN), ('pressed', self.ACCENT_GREEN), ('active', self.ACCENT_DARK)],
              background=[('active', self.BG_DARK)],
              foreground=[('disabled', self.ERROR_RED),  # <-- Red when disabled (mutually exclusive)
                          ('selected', self.ACCENT_GREEN),    # <-- Green when checked
                          ('active', self.ACCENT_GREEN)]      # <-- Green on hover
              )
        # ---------------------------------------------------------

        s.configure("TLabelframe", background=self.BG_DARK, foreground=self.ACCENT_GREEN, bordercolor=self.ACCENT_DARK)
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

    # --- SECURITY: Shell Injection Prevention ---
    def _sanitize_for_shell(self, value):
        """
        Safely escapes a value for shell command use.
        Uses shlex.quote() to prevent command injection attacks.
        
        Args:
            value: String to sanitize
            
        Returns:
            Safely quoted string ready for shell use
            
        Example:
            >>> _sanitize_for_shell("test'; rm -rf /")
            'test'"'"'; rm -rf /'  # Now safe - literal string, not code
        """
        if not value:
            return value
        
        str_value = str(value)
        
        # Prevent DoS via extremely long inputs (Linux ARG_MAX is ~2MB)
        MAX_LENGTH = 8000
        if len(str_value) > MAX_LENGTH:
            # Silently truncate instead of crashing
            # The widget validation already warned the user
            return shlex.quote(str_value[:MAX_LENGTH])
        
        return shlex.quote(str_value)
        # --- End Security Method ---
    
    # --- AUTO-CLOSE HANDLER ---
    def _auto_close_msg(self, event):
        """Closes the custom message window if it exists and the user clicks main window."""
        if hasattr(self, '_current_msg') and self._current_msg and self._current_msg.winfo_exists():
             self._current_msg.destroy()
             self._current_msg = None
             
    def _on_background_click(self, event):
        """Clears focus when clicking on non-interactive background widgets."""
        # Check if the clicked widget is just a layout container or label
        if event.widget.winfo_class() in ('TFrame', 'Frame', 'TLabel', 'Label', 'Canvas', 'TPanedwindow'):
             # Force focus to the main window, effectively "unfocusing" entry boxes
             self.root.focus_set()

    # --- CUSTOM THEMED MESSAGE BOX ---
    def _show_styled_message(self, title, message, is_warning=False):
        """Displays a non-modal, themed message box that auto-closes on outside click."""
        # Close any existing message first
        self._auto_close_msg(None)

        msg_win = tk.Toplevel(self.root)
        msg_win.title(title)
        msg_win.transient(self.root) 
        msg_win.configure(bg=self.BG_DARK)

        # Calculate center position relative to main window
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        
        mw, mh = 500, 220
        # -------------------------
        
        msg_win.geometry(f"{mw}x{mh}+{rx + (rw//2 - mw//2)}+{ry + (rh//2 - mh//2)}")
        
        accent = self.ERROR_RED if is_warning else self.ACCENT_GREEN

        title_label = ttk.Label(msg_win, text=title, font=("Helvetica", 14, "bold"), foreground=accent)
        title_label.pack(pady=(30, 15), padx=20)

        msg_label = ttk.Label(msg_win, text=message, wraplength=460, justify="center", font=("Helvetica", 11))
        msg_label.pack(pady=(0, 30), padx=20, expand=True)

        ok_btn = ttk.Button(msg_win, text="OK", command=msg_win.destroy, style="TButton")
        ok_btn.pack(pady=(0, 30), ipadx=10)
        
        ok_btn.focus_set()
        msg_win.bind("<Return>", lambda e: msg_win.destroy())
        msg_win.bind("<Escape>", lambda e: msg_win.destroy())

        self._current_msg = msg_win


    # --- Helper method for days and dates ---
    def _update_days_for_date_widget(self, year_var, month_var, day_var, day_combo):
        """Helper function to update the day Combobox based on selected month/year."""
        try:
            year_str = year_var.get()
            month_str = month_var.get()

            if year_str and month_str:
                year = int(year_str)
                month = int(month_str.split("-")[0]) # "02-Feb" -> 02
                
                num_days = calendar.monthrange(year, month)[1]
                
                new_day_list = [""] + [f"{i:02d}" for i in range(1, num_days + 1)]
                
                current_day = day_var.get()
                day_combo['values'] = new_day_list

                if current_day not in new_day_list:
                    day_var.set("")
            else:
                default_days = [""] + [f"{i:02d}" for i in range(1, 32)]
                day_combo['values'] = default_days
        except ValueError:
            default_days = [""] + [f"{i:02d}" for i in range(1, 32)]
            day_combo['values'] = default_days
        
        self._on_form_change()
    
    
    # --- UI & Event Handlers ---
    def _open_url(self, url):
        """Safely opens a URL in the default web browser."""
        if url.startswith("http://") or url.startswith("https://"):
            webbrowser.open_new_tab(url)
           
    # --- PATH SETTER HELPER --- 
    def _set_path(self, var, path):
        """Updates variable with POSIX-style path only if valid."""
        if not path:
            return
        
        # Validate characters
        is_valid, error_msg = self._validate_path_chars(path)
        if not is_valid:
            self._show_styled_message("Invalid Path", error_msg, is_warning=True)
            return
        
        var.set(Path(path).as_posix())
             
    def _show_text_logo_fallback(self, parent_frame):
        """Displays text when the logo image cannot be loaded."""
        fallback_label = ttk.Label(parent_frame, text="L-COMMANDER", style="Title.TLabel", font=("Helvetica", 20, "bold"))
        fallback_label.pack(anchor="w", padx=(10, 0), pady=(10, 15))

    # --- HELPER: Validation for number_input ---
    def _validate_numeric_input(self, P):
        """Validates that the input is a digit or empty."""
        if P.isdigit() or P == "":
            return True
        return False

    def _on_form_mousewheel(self, event):
        scroll_region = self.form_canvas.bbox("all")
        if scroll_region:
            content_height = scroll_region[3] - scroll_region[1]
            canvas_height = self.form_canvas.winfo_height()
            if content_height > canvas_height:
                self.form_canvas.focus_set()
                self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # --- Recursive Mousewheel Binding ---
    def _bind_mousewheel_recursive(self, widget):
            if widget.winfo_class() == 'TCombobox':
                widget.bind('<MouseWheel>', lambda e: "break")
            else:
                widget.bind('<MouseWheel>', self._on_form_mousewheel)
                
            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child)

    def _on_tree_keypress(self, event):
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock'):
            return
        if event.keysym == 'BackSpace':
            current_text = self.search_var.get()
            self.search_var.set(current_text[:-1])
        elif event.char and event.char.isprintable():
            self.search_var.set(self.search_var.get() + event.char)
        else:
            return
        self.search_entry.focus_set()
        self.search_entry.icursor(tk.END)
        return "break"

    def _on_escape(self, event):
        self.search_var.set("")
        self.command_tree.focus_set()

    def _setup_main_ui(self):
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left frame with a fixed width that fits your longest text
        left_frame = ttk.Frame(main_container, width=240)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        # Prevent it from shrinking if its content is smaller
        left_frame.pack_propagate(False)
        
        # --- LOGO INTEGRATION START (Multi-Size Icons) ---
        if logo_path.exists():
            try:
                # 1. Load original image with Pillow
                original_image = Image.open(logo_path)

                # 2. Create MULTIPLE icon sizes for best quality everywhere
                icon_16 = ImageTk.PhotoImage(original_image.resize((16, 16), Image.Resampling.LANCZOS))
                icon_32 = ImageTk.PhotoImage(original_image.resize((32, 32), Image.Resampling.LANCZOS))
                icon_48 = ImageTk.PhotoImage(original_image.resize((48, 48), Image.Resampling.LANCZOS))
                icon_64 = ImageTk.PhotoImage(original_image.resize((64, 64), Image.Resampling.LANCZOS))

                # Pass ALL of them to iconphoto.
                self.icon_images = [icon_16, icon_32, icon_48, icon_64] 
                self.root.iconphoto(True, *self.icon_images)

                # 3. Create the version for the sidebar (68x68)
                sidebar_resized = original_image.resize((68, 68), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(sidebar_resized)

                # 4. Display sidebar logo
                logo_label = ttk.Label(left_frame, image=self.logo_img)
                logo_label.pack(anchor="w", padx=(10, 0), pady=(0, 0))

            except Exception as e:
                print(f"Error loading logo: {e}")
                
        else:
            # Fallback if file is missing entirely
            self._show_text_logo_fallback(left_frame)
        # --- LOGO INTEGRATION END ---
        
        list_label = ttk.Label(left_frame, text="Commands", style="Title.TLabel")
        list_label.pack(pady=(0, 5), anchor="w")
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_tree())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X)
        ttk.Label(search_frame, text="Search...", style="Tooltip.TLabel").pack(anchor="w")
        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        self.command_tree = ttk.Treeview(tree_container, show="tree")
        
        # --- Smooth Scrolling (Stabilized with Focus) ---
        def _on_tree_mousewheel(event):
            # 1. Force focus to the tree. This stops the "hover" highlight 
            #    from fighting with the scroll action.
            self.command_tree.focus_set()
            
            # 2. Determine direction
            direction = -1 if event.delta > 0 else 1
            
            # 3. Keep your preferred speed
            speed = 2 
            
            self.command_tree.yview_scroll(direction * speed, "units")
            return "break"
        
        self.command_tree.bind("<MouseWheel>", _on_tree_mousewheel)
        # -------------------------------------------------------
        
        tree_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.command_tree.yview)
        self.command_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.command_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.command_tree.bind("<Key>", self._on_tree_keypress)
        self.root.bind("<Escape>", self._on_escape)
        self.command_tree.bind("<<TreeviewSelect>>", self.on_command_select)
        
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(right_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        self.title_label = ttk.Label(title_frame, text="", style="Title.TLabel")
        self.title_label.pack(anchor="w")
        self.desc_label = ttk.Label(title_frame, text="Select a command from the tree.", wraplength=600, justify=tk.LEFT, style="Description.TLabel")
        self.desc_label.pack(anchor="w", pady=(5, 0))
        self.example_label = ttk.Label(title_frame, text="", wraplength=600, justify=tk.LEFT, style="Example.TLabel")
        self.example_label.pack(anchor="w", pady=(5,0))
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.sudo_frame = ttk.Frame(right_frame)
        self.sudo_frame.pack(fill=tk.X, pady=(0, 5))
        form_container = ttk.Frame(right_frame)
        form_container.pack(fill=tk.BOTH, expand=True)
        
        # Apply theme to Canvas manually (ttk styles don't fully cover it)
        self.form_canvas = tk.Canvas(form_container, highlightthickness=0, bg=self.BG_DARK)
        
        self.form_canvas.bind('<MouseWheel>', self._on_form_mousewheel)
        form_scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=self.form_canvas.yview)
        self.form_frame = ttk.Frame(self.form_canvas)
        self.form_frame.bind("<Configure>", lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")))
        self.form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.form_canvas.configure(yscrollcommand=form_scrollbar.set)
        self.form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Separator(bottom_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        output_label = ttk.Label(bottom_frame, text="Generated Command:", style="Section.TLabel")
        output_label.pack(anchor="w", pady=(0, 5))

        # Apply theme to the Output Text Box manually
        self.cmd_box = tk.Text(bottom_frame, height=4, state="disabled", 
                               background=self.BG_DARKER, foreground=self.ACCENT_GREEN, 
                               insertbackground=self.ACCENT_GREEN, # Cursor color
                               font=("Courier", 11), relief="flat", highlightthickness=1, highlightbackground=self.ACCENT_DARK)

        self.cmd_box.pack(fill=tk.X)
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        copy_button = ttk.Button(button_frame, text="Copy Command", command=self.copy_command)
        copy_button.pack(side=tk.RIGHT)
        clear_button = ttk.Button(button_frame, text="Clear Form", command=self.clear_form)
        clear_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # edit
        # --- AI ANALYZER BUTTON ---
        if AI_AVAILABLE:
            analyze_button = ttk.Button(button_frame, text="Analyze with AI 🤖", command=self.analyze_with_ai)
        else:
            analyze_button = ttk.Button(button_frame, text="AI Unavailable ⚠️", state="disabled", style="DisabledRed.TButton")
        analyze_button.pack(side=tk.RIGHT, padx=(0, 5))

        # --- SETTINGS BUTTON ---
        if SETTINGS_AVAILABLE and AI_AVAILABLE:
            settings_btn = ttk.Button(button_frame, text="AI Settings ⚙️", command=self.open_settings)
        else:
            settings_btn = ttk.Button(button_frame, text="Settings ⚠️", state="disabled", style="DisabledRed.TButton")
        settings_btn.pack(side=tk.RIGHT, padx=(0, 5))

        # --- UPDATE MANAGER BUTTON ---
        if UPDATE_MANAGER_AVAILABLE and self.update_manager:
            update_btn = ttk.Button(button_frame, text="Check Updates 🔄", command=self.open_update_manager)
        else:
            update_btn = ttk.Button(button_frame, text="Updates ⚠️", state="disabled", style="DisabledRed.TButton")
        update_btn.pack(side=tk.RIGHT, padx=(0, 5))

    # --- SETTINGS PANEL OPENER ---
    def open_settings(self):
        """Opens the AI settings configuration panel."""
        if not SETTINGS_AVAILABLE:
             self._show_styled_message("Error", "Settings panel module is missing.", is_warning=True)
             return
        settings_panel.SettingsPanel(self.root)

    # --- UPDATE MANAGER OPENER ---
    def open_update_manager(self):
        """Opens the update manager window."""
        if not UPDATE_MANAGER_AVAILABLE:
            self._show_styled_message("Error", 
                "Update manager module is missing.", is_warning=True)
            return
        
        if self.update_manager:
            self.update_manager.open_update_window()
        else:
            self._show_styled_message("Error", 
                "Update manager failed to initialize.", is_warning=True)

    # --- AI ANALYZER OPENER ---
    def analyze_with_ai(self):
        if not AI_AVAILABLE:
             self._show_styled_message("Error", "AI analyzer module is missing.", is_warning=True)
             return
        command = self.cmd_box.get(1.0, tk.END).strip()
        if not command or command == self.current_command_info.get("name"):
            # --- Use custom message instead of native messagebox ---
            self._show_styled_message("Incomplete Command", "Please build a more complete command to analyze.", is_warning=True)
            return

        # --- Close previous result window if it exists ---
        if self.ai_result_window and self.ai_result_window.winfo_exists():
            self.ai_result_window.destroy()
        # ----------------------------------------------------

        # 1. COORDINATES & DEFAULTS
        self.root.update_idletasks()
        main_x, main_y = self.root.winfo_x(), self.root.winfo_y()
        main_w, main_h = self.root.winfo_width(), self.root.winfo_height()

        splash_w, splash_h = 400, 120
        splash_img = None
        
        # 2. LOAD & RESIZE LOGO FOR SPLASH
        if logo_path.exists():
            try:
                pil_img = Image.open(logo_path)
                target_w, target_h = pil_img.width // 2, pil_img.height // 2
                resized_pil = pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                splash_img = ImageTk.PhotoImage(resized_pil)
                splash_w, splash_h = target_w, target_h
            except Exception as e:
                print(f"Logo load error (using fallback): {e}")

        # 3. CREATE SPLASH WINDOW
        s_x = main_x + (main_w // 2) - (splash_w // 2)
        s_y = main_y + (main_h // 2) - (splash_h // 2)

        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.geometry(f"{splash_w}x{splash_h}+{int(s_x)}+{int(s_y)}")
        
        # Splash Border & Theme
        splash.configure(background=self.ACCENT_GREEN)
        canvas = tk.Canvas(splash, width=splash_w, height=splash_h, 
                           bg=self.BG_DARKER, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # 4. DRAW CONTENT
        if splash_img:
            self.splash_img = splash_img 
            canvas.create_image(splash_w//2, splash_h//2, image=self.splash_img, anchor="center")
            canvas.create_text(splash_w//2, splash_h - 20, 
                               text="Analyzing command, please wait...", 
                               fill=self.FG_LIGHT, font=("Helvetica", 11))
        else:
            canvas.create_text(splash_w//2, splash_h//2 - 15,
                               text="L-COMMANDER",
                               fill=self.ACCENT_GREEN, font=("Helvetica", 24, "bold"))
            canvas.create_text(splash_w//2, splash_h//2 + 20,
                               text="Analyzing command...",
                               fill=self.FG_LIGHT, font=("Helvetica", 12))

        splash.grab_set()
        self.root.update()

        # 5. RESULT WINDOW SETUP
        r_w, r_h = 600, 500
        r_x = main_x + (main_w // 2) - (r_w // 2)
        r_y = main_y + (main_h // 2) - (r_h // 2)
        
        # --- Use self.ai_result_window instead of local variable ---
        self.ai_result_window = tk.Toplevel(self.root)
        self.ai_result_window.title(f"AI Analysis: {self.current_command_info.get('name')}")
        self.ai_result_window.transient(self.root)
        self.ai_result_window.geometry(f"{r_w}x{r_h}+{int(r_x)}+{int(r_y)}")
        self.ai_result_window.configure(bg=self.BG_DARK)
        self.ai_result_window.withdraw()
        
        # Use self.ai_result_window as parent for the text widget
        result_text = scrolledtext.ScrolledText(self.ai_result_window, wrap=tk.WORD, font=("Helvetica", 10),
                                                bg=self.BG_DARKER, fg=self.FG_LIGHT, 
                                                insertbackground=self.ACCENT_GREEN, relief="flat")
        result_text.pack(expand=True, fill="both", padx=10, pady=10)
        # --------------------------------------------------------------------

        # 6. RUN AI & SWAP (WITH ERROR HANDLING)
        try:
            ai_response = ai_analyzer.analyze_command(command)
        except Exception as e:
            ai_response = f"❌ **AI Analysis Failed**\n\nError details:\n{str(e)}\n\nPlease check your settings and internet connection."

        splash.grab_release()
        splash.destroy()
        self.ai_result_window.deiconify()

        # 7. POPULATE RESULTS
        result_text.insert(tk.END, ai_response)
        result_text.tag_configure("hyperlink", foreground="#4fc3f7", underline=True)
        url_pattern = re.compile(r"https?://[^\s]+")
        content = result_text.get("1.0", tk.END)
        for match in url_pattern.finditer(content):
            start, end = match.span()
            url = match.group(0)
            start_idx = result_text.index(f"1.0 + {start} chars")
            end_idx = result_text.index(f"1.0 + {end} chars")
            result_text.tag_add("hyperlink", start_idx, end_idx)
            result_text.tag_bind("hyperlink", "<Button-1>", lambda e, link=url: self._open_url(link))
            result_text.tag_bind("hyperlink", "<Enter>", lambda e: result_text.config(cursor="hand2"))
            result_text.tag_bind("hyperlink", "<Leave>", lambda e: result_text.config(cursor=""))
        result_text.config(state="disabled")
        
    def _populate_command_tree(self):
        for category_name in sorted(self.COMMANDS_DATA.keys()):
            commands = self.COMMANDS_DATA[category_name]
            self.command_tree.insert("", "end", text=category_name, iid=category_name, open=True)
            for command_name in sorted(commands.keys()):
                self.command_tree.insert(category_name, "end", text=command_name, iid=command_name)

    def _filter_tree(self):
        search_text = self.search_var.get().lower()
        for item in self.command_tree.get_children(): self.command_tree.delete(item)
        for category_name in sorted(self.COMMANDS_DATA.keys()):
            commands = self.COMMANDS_DATA[category_name]
            is_category_match = search_text in category_name.lower()
            matching_commands = [name for name in sorted(commands.keys()) if search_text in name.lower() or search_text in commands[name].get("description", "").lower() or search_text in commands[name].get("example", "").lower()]
            if not search_text or is_category_match or matching_commands:
                cat_id = self.command_tree.insert("", "end", text=category_name, iid=category_name, open=True)
                if not search_text or is_category_match: commands_to_show = sorted(commands.keys())
                else: commands_to_show = matching_commands
                for command_name in commands_to_show: self.command_tree.insert(cat_id, "end", text=command_name, iid=command_name)
    
    # --- clear_form ---
    def clear_form(self):
        for item in self.widget_vars:
            item_type = item.get("type", "text")
            clearer_func = self._widget_clearers.get(item_type, self._clear_widget_text)
            clearer_func(item)

        if self.permission_vars:
            for category in self.permission_vars.values():
                for perm_var in category.values(): perm_var.set(False)
        self.sudo_var.set(False)
        self._on_form_change()

    def on_command_select(self, event):
        selected_id = self.command_tree.focus()
        if not selected_id or not self.command_tree.parent(selected_id): return
        
        command_name = selected_id
        category_name = self.command_tree.parent(selected_id)
        
        self.current_command_info = { "name": command_name, "data": self.COMMANDS_DATA[category_name][command_name] }
        
        for widget in self.form_frame.winfo_children(): widget.destroy()
        for widget in self.sudo_frame.winfo_children(): widget.destroy()
        self.widget_vars.clear()
        self.permission_vars.clear()
        self.sudo_var.set(False)

        self.title_label.config(text=f"Command: {command_name}")
        self.desc_label.config(text=self.current_command_info["data"].get("description", ""))
        
        example = self.current_command_info["data"].get("example")
        self.example_label.config(text=f"Example: {example}" if example else "")

        if self.current_command_info["data"].get("requires_sudo"):
            sudo_check = ttk.Checkbutton(self.sudo_frame, text="Run with sudo", variable=self.sudo_var, style="Sudo.TCheckbutton", command=self._on_form_change)
            sudo_check.pack(anchor="w")
        elif self.current_command_info["data"].get("sudo_optional"):
            sudo_check = ttk.Checkbutton(self.sudo_frame, text="Run with sudo", variable=self.sudo_var, command=self._on_form_change)
            sudo_check.pack(anchor="w")

        self.build_form()
        self._on_form_change()

    def _on_form_change(self, *args):
        self._update_widget_states()
        self.update_command_display()

    # --- _update_widget_states (and its helpers) ---
    def _is_active_checkbox(self, item):
        return item.get("var") and item["var"].get()

    def _is_active_url(self, item):
        return item.get("url_var") and item["url_var"].get().strip()

    def _is_active_file_w_ext(self, item):
        return item.get("base_var") and item["base_var"].get().strip()

    def _is_active_var(self, item):
        return item.get("var") and item["var"].get().strip()

    def _is_active_num_var(self, item):
        return item.get("num_var") and item["num_var"].get().strip()

    def _is_active_date_input(self, item):
        return (item.get("year_var") and item["year_var"].get() and
                item.get("month_var") and item["month_var"].get() and
                item.get("day_var") and item["day_var"].get())

    def _update_widget_states(self):
        flags_to_disable = set()
        should_disable_sudo = False

        for item in self.widget_vars:
            item_type = item.get("type", "text")
            
            is_active_func = self._widget_active_checkers.get(item_type, self._is_active_var)
            is_active = is_active_func(item)

            if is_active and "disables" in item:
                for flag in item["disables"]:
                    flags_to_disable.add(flag)
            
            if is_active and item.get("disables_sudo_checkbox"):
                should_disable_sudo = True

        if self.sudo_frame.winfo_children():
            sudo_widget = self.sudo_frame.winfo_children()[0]
            if should_disable_sudo:
                self.sudo_var.set(False)
                sudo_widget.config(state=tk.DISABLED)
            else:
                sudo_widget.config(state=tk.NORMAL)

        is_sudo_active = self.sudo_var.get()

        for item in self.widget_vars:
            widget = item.get("widget")
            if not widget: continue

            flag = item.get("flag", "")
            
            is_disabled_by_peer = flag in flags_to_disable
            is_disabled_by_sudo = (is_sudo_active and item.get("disable_if_sudo"))

            if is_disabled_by_peer or is_disabled_by_sudo:
                widget.config(state=tk.DISABLED)
            else:
                if widget.winfo_class() == 'TCombobox':
                    widget.config(state='readonly')
                else:
                    widget.config(state=tk.NORMAL)

    # --- build_form ---
    def build_form(self):
        for field_data in self.current_command_info["data"]["fields"]:
            frame = ttk.Frame(self.form_frame)
            frame.pack(fill=tk.X, pady=4)
            widget_frame = ttk.Frame(frame)
            widget_frame.pack(fill=tk.X)
            
            widget_data = field_data.copy()
            if 'type' not in widget_data:
                widget_data['type'] = 'text'
            
            field_type = widget_data['type']
            
            builder_func = self._widget_builders.get(field_type, self._build_widget_text)
            builder_func(widget_frame, widget_data)
            
            if "tooltip" in field_data:
                tooltip_label = ttk.Label(frame, text=field_data["tooltip"], style="Tooltip.TLabel")
                tooltip_label.pack(fill=tk.X, padx=(25, 10), pady=(0, 0))
                
        self._bind_mousewheel_recursive(self.form_frame)

    # --- update_command_display ---
    def update_command_display(self, *args):
        if not self.current_command_info: return
        
        command_name = self.current_command_info["name"]
        prefix = "sudo " if self.sudo_var.get() else ""
        flagged_args = []
        positional_args = []
        stderr_redirect = "" 

        if command_name == "chmod" and self.permission_vars:
            mode = ""
            for cat in ['user', 'group', 'other']:
                val = 0
                if self.permission_vars[cat]['r'].get(): val += 4
                if self.permission_vars[cat]['w'].get(): val += 2
                if self.permission_vars[cat]['x'].get(): val += 1
                mode += str(val)
            if mode != "000":
                positional_args.append(mode)

        for item in self.widget_vars:
            widget = item.get("widget")
            if widget and widget.cget("state") == tk.DISABLED:
                continue

            item_type = item.get("type", "text")
            
            arg_getter = self._widget_arg_getters.get(item_type, self._get_arg_from_text)
            arg_data = arg_getter(item, command_name)

            if arg_data:
                if arg_data.get("is_stderr_redirect"):
                    stderr_redirect = arg_data["arg"]
                elif not arg_data["flag"]:
                    positional_args.append(arg_data["arg"])
                else:
                    flagged_args.append(arg_data["arg"])

        if command_name == "find":
            command_parts = [f"{prefix}{command_name}"] + positional_args + flagged_args
        else:
            command_parts = [f"{prefix}{command_name}"] + flagged_args + positional_args
        
        final_command = " ".join(part for part in command_parts if part)
        final_command += stderr_redirect 

        self.cmd_box.config(state="normal")
        self.cmd_box.delete(1.0, tk.END)
        self.cmd_box.insert(1.0, final_command)
        self.cmd_box.config(state="disabled")

    def copy_command(self):
        command = self.cmd_box.get(1.0, tk.END).strip()
        if not command or command == self.current_command_info.get("name"):
            self._show_styled_message("No Command", "The command is not complete yet!", is_warning=True)
            return
        pyperclip.copy(command)
        self._show_styled_message("Copied!", f"Copied to clipboard:\n\n{command}")

    # --- Helper Methods for Building Widgets ---

    def _build_permission_grid(self, parent_frame, widget_data):
        self.permission_vars = {
            'user': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()},
            'group': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()},
            'other': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()}
        }
        main_frame = ttk.Frame(parent_frame)
        main_frame.pack(fill=tk.X)
        categories = {'User': 'user', 'Group': 'group', 'Other': 'other'}
        permissions = {'Read': 'r', 'Write': 'w', 'Execute': 'x'}
        for i, (cat_label, cat_key) in enumerate(categories.items()):
            labelframe = ttk.LabelFrame(main_frame, text=cat_label)
            labelframe.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            for perm_label, perm_key in permissions.items():
                chk = ttk.Checkbutton(labelframe, text=perm_label, variable=self.permission_vars[cat_key][perm_key], command=self._on_form_change)
                chk.pack(anchor="w", padx=10)

    def _build_widget_checkbox(self, parent_frame, widget_data):
        var = tk.BooleanVar()
        chk = ttk.Checkbutton(parent_frame, text=widget_data["label"], variable=var, command=self._on_form_change)
        chk.pack(anchor="w")
        widget_data.update({"var": var, "widget": chk})
        self.widget_vars.append(widget_data)

    def _build_widget_dropdown(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        var = tk.StringVar()
        combo = ttk.Combobox(parent_frame, textvariable=var, values=widget_data.get("options", []), state="readonly", width=30)
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        combo.bind("<<ComboboxSelected>>", self._on_form_change)
        widget_data.update({"var": var, "widget": combo})
        self.widget_vars.append(widget_data)

    def _build_widget_size_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        size_frame = ttk.Frame(parent_frame)
        size_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        op_var = tk.StringVar()
        op_combo = ttk.Combobox(size_frame, textvariable=op_var, values=["", "+", "-"], state="readonly", width=3)
        op_combo.pack(side=tk.LEFT)
        op_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        num_var = tk.StringVar()
        num_var.trace_add("write", lambda n, i, m: self._on_form_change())
        num_entry = ttk.Entry(size_frame, textvariable=num_var, width=10)
        num_entry.pack(side=tk.LEFT, padx=(5, 0))
        unit_var = tk.StringVar()
        unit_options = widget_data.get("options", ["c", "k", "M", "G"]) 
        unit_combo = ttk.Combobox(size_frame, textvariable=unit_var, values=unit_options, state="readonly", width=5)
        unit_combo.pack(side=tk.LEFT, padx=(5, 0))
        unit_combo.set(unit_options[0] if unit_options else "") 
        unit_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        widget_data.update({"op_var": op_var, "num_var": num_var, "unit_var": unit_var, "widget": num_entry})
        self.widget_vars.append(widget_data)

    def _build_widget_relative_time_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        time_frame = ttk.Frame(parent_frame)
        time_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        op_var = tk.StringVar()
        op_combo = ttk.Combobox(time_frame, textvariable=op_var, values=["", "+", "-"], state="readonly", width=3)
        op_combo.pack(side=tk.LEFT)
        op_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        num_var = tk.StringVar()
        num_var.trace_add("write", lambda n, i, m: self._on_form_change())
        num_entry = ttk.Entry(time_frame, textvariable=num_var, width=10)
        num_entry.pack(side=tk.LEFT, padx=(5, 0))
        widget_data.update({"op_var": op_var, "num_var": num_var, "widget": num_entry})
        self.widget_vars.append(widget_data)

    def _build_widget_notable_text_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        not_frame = ttk.Frame(parent_frame)
        not_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        not_var = tk.StringVar()
        not_combo = ttk.Combobox(not_frame, textvariable=not_var, values=["", "!"], state="readonly", width=3)
        not_combo.pack(side=tk.LEFT)
        not_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        entry = ttk.Entry(not_frame, textvariable=var, width=20)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        widget_data.update({"not_var": not_var, "var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_permission_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        perm_frame = ttk.Frame(parent_frame)
        perm_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        mode_var = tk.StringVar()
        mode_options = [" (exact)", "- (at least)", "/ (any of)"]
        mode_combo = ttk.Combobox(perm_frame, textvariable=mode_var, values=mode_options, state="readonly", width=12)
        mode_combo.pack(side=tk.LEFT)
        mode_combo.set(mode_options[0]) 
        mode_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        entry = ttk.Entry(perm_frame, textvariable=var, width=15)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        widget_data.update({"mode_var": mode_var, "var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_date_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        date_frame = ttk.Frame(parent_frame)
        date_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        not_var = tk.StringVar()
        not_combo = ttk.Combobox(date_frame, textvariable=not_var, values=["", "!"], state="readonly", width=3)
        not_combo.pack(side=tk.LEFT)
        year_var = tk.StringVar()
        current_year = datetime.date.today().year
        
        # Configurable range (default past 50 years + next 5)
        min_year = widget_data.get("min_year", current_year - 50)
        max_year = widget_data.get("max_year", current_year + 5)
        
        year_list = [""] + list(range(max_year, min_year - 1, -1))
        year_combo = ttk.Combobox(date_frame, textvariable=year_var, values=year_list, state="readonly", width=6)
        year_combo.pack(side=tk.LEFT, padx=(5, 0))
        month_var = tk.StringVar()
        month_list = ["", "01-Jan", "02-Feb", "03-Mar", "04-Apr", "05-May", "06-Jun", 
                      "07-Jul", "08-Aug", "09-Sep", "10-Oct", "11-Nov", "12-Dec"]
        month_combo = ttk.Combobox(date_frame, textvariable=month_var, values=month_list, state="readonly", width=8)
        month_combo.pack(side=tk.LEFT, padx=(5, 0))
        day_var = tk.StringVar()
        day_list = [""] + [f"{i:02d}" for i in range(1, 32)]
        day_combo = ttk.Combobox(date_frame, textvariable=day_var, values=day_list, state="readonly", width=4)
        day_combo.pack(side=tk.LEFT, padx=(5, 0))
        year_combo.bind("<<ComboboxSelected>>", lambda e: self._update_days_for_date_widget(year_var, month_var, day_var, day_combo))
        month_combo.bind("<<ComboboxSelected>>", lambda e: self._update_days_for_date_widget(year_var, month_var, day_var, day_combo))
        day_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        not_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        widget_data.update({
            "not_var": not_var, 
            "year_var": year_var,
            "month_var": month_var,
            "day_var": day_var,
            "widget": year_combo,
            "day_combo_widget": day_combo
        })
        self.widget_vars.append(widget_data)
        
    def _validate_path_chars(self, path):
        """Check for invalid filesystem characters."""
        # These are invalid on Windows/Linux/Mac
        invalid_chars = '<>:"|?*'
        
        for char in invalid_chars:
            if char in path:
                return False, f"Path contains invalid character: '{char}'"
        
        # Check for invalid names on Windows
        invalid_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                        'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                        'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_only = Path(path).name.upper().split('.')[0]
        if name_only in invalid_names:
            return False, f"'{name_only}' is a reserved system name"
        
        return True, ""

    def _build_widget_url(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        url_frame = ttk.Frame(parent_frame)
        url_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        protocol_var = tk.StringVar(value="https://")
        protocol_combo = ttk.Combobox(url_frame, textvariable=protocol_var, values=["https://", "http://"], width=8, state="readonly")
        protocol_combo.pack(side=tk.LEFT)
        protocol_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        url_var = tk.StringVar()
        url_var.trace_add("write", lambda n, i, m: self._on_form_change())
        url_entry = ttk.Entry(url_frame, textvariable=url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        widget_data.update({"protocol_var": protocol_var, "url_var": url_var, "widget": url_entry})
        self.widget_vars.append(widget_data)

    def _build_widget_file_w_ext(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        file_frame = ttk.Frame(parent_frame)
        file_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        base_var = tk.StringVar()
        base_var.trace_add("write", lambda n, i, m: self._on_form_change())
        base_entry = ttk.Entry(file_frame, textvariable=base_var)
        base_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ext_var = tk.StringVar()
        options = widget_data.get("options", [])
        if options:
            ext_combo = ttk.Combobox(file_frame, textvariable=ext_var, values=options, state="readonly", width=10)
            ext_combo.pack(side=tk.LEFT)
            ext_combo.set(options[0])
            ext_combo.bind("<<ComboboxSelected>>", self._on_form_change)
        widget_data.update({"base_var": base_var, "ext_var": ext_var, "widget": base_entry})
        self.widget_vars.append(widget_data)

    # edit
    def _build_widget_text(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        var = tk.StringVar()
        entry = ttk.Entry(parent_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Add validation feedback label
        feedback_label = ttk.Label(parent_frame, text="", style="Tooltip.TLabel")
        
        # Debounce timer to prevent lag
        validation_timer = None
        
        def validate_on_change(*args):
            nonlocal validation_timer
            
            # Cancel previous timer if user is still typing
            if validation_timer:
                self.root.after_cancel(validation_timer)
            
            value = var.get()
            max_len = widget_data.get("max_length", 500)
            
            # Instant visual feedback for length check
            if len(value) > max_len:
                feedback_label.config(
                    text=f"⚠️ Too long ({len(value)}/{max_len})", 
                    foreground=self.ERROR_RED
                )
                entry.config(style="Invalid.TEntry")
            else:
                feedback_label.config(text="")
                entry.config(style="TEntry")
            
            # Debounce the heavy command update (300ms delay)
            validation_timer = self.root.after(300, self._on_form_change)
        
        var.trace_add("write", validate_on_change)
        feedback_label.pack(fill=tk.X, padx=(25, 10))
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_file_picker(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        picker_frame = ttk.Frame(parent_frame)
        picker_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        button = ttk.Button(picker_frame, text="Browse...", 
                       command=lambda: self._set_path(var, filedialog.askopenfilename()))
        
        button.pack(side=tk.LEFT, padx=(5, 0))
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_dir_picker(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        picker_frame = ttk.Frame(parent_frame)
        picker_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        button = ttk.Button(picker_frame, text="Browse...", 
                       command=lambda: self._set_path(var, filedialog.askdirectory()))
        
        button.pack(side=tk.LEFT, padx=(5, 0))
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_file_save_as(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        picker_frame = ttk.Frame(parent_frame)
        picker_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        button = ttk.Button(picker_frame, text="Save As...", 
                       command=lambda: self._set_path(var, filedialog.asksaveasfilename()))
        
        button.pack(side=tk.LEFT, padx=(5, 0))
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    def _build_widget_number_input(self, parent_frame, widget_data):
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self._on_form_change())
        
        # Get bounds from widget_data
        min_val = widget_data.get("min", 0)
        max_val = widget_data.get("max", 999999)
        
        # Enhanced validation with bounds
        def validate_bounded_number(P):
            if P == "":
                return True
            if not P.isdigit():
                return False
            try:
                num = int(P)
                return min_val <= num <= max_val
            except ValueError:
                return False
        
        vcmd = (self.root.register(validate_bounded_number), '%P')
        entry = ttk.Entry(parent_frame, textvariable=var, validate="key", validatecommand=vcmd)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)

    # --- Helper Methods for Clearing Widgets ---

    def _clear_widget_checkbox(self, item):
        item["var"].set(False)

    def _clear_widget_size_input(self, item):
        item["op_var"].set("")
        item["num_var"].set("")
        options = item.get("options", [])
        item["unit_var"].set(options[0] if options else "")

    def _clear_widget_relative_time_input(self, item):
        item["op_var"].set("")
        item["num_var"].set("")

    def _clear_widget_notable_text_input(self, item):
        item["not_var"].set("")
        item["var"].set("")

    def _clear_widget_permission_input(self, item):
        item["mode_var"].set(" (exact)")
        item["var"].set("")

    def _clear_widget_date_input(self, item):
        item["not_var"].set("")
        item["year_var"].set("")
        item["month_var"].set("")
        item["day_var"].set("")
        default_days = [""] + [f"{i:02d}" for i in range(1, 32)]
        item["day_combo_widget"]['values'] = default_days

    def _clear_widget_url(self, item):
        item["protocol_var"].set("https://")
        item["url_var"].set("")

    def _clear_widget_file_w_ext(self, item):
        item["base_var"].set("")
        if item.get("ext_var"): 
            options = item.get("options", [])
            item["ext_var"].set(options[0] if options else "")

    def _clear_widget_text(self, item):
        if "var" in item:
            item["var"].set("")

    # --- Helper Methods for Getting Command Arguments ---
    def _get_arg_from_checkbox(self, item, command_name):
        """Checkbox arguments (flags only, no user input)"""
        if not item["var"].get():
            return None
        
        flag = item.get("flag", "")
        if flag == "redirect_stderr":
            return {"arg": " 2>/dev/null", "flag": flag, "is_stderr_redirect": True}
        
        # Flags are predefined, not user input, so safe
        return {"arg": flag, "flag": flag}

    def _get_arg_from_size_input(self, item, command_name):
        """Size input: operator + number + unit"""
        op = item["op_var"].get()  # Dropdown: "", "+", "-" (safe)
        num = item["num_var"].get().strip()
        unit = item["unit_var"].get()  # Dropdown: "c", "k", "M", "G" (safe)
        
        if num and unit:
            # SANITIZE: User can type arbitrary numbers
            num_safe = self._sanitize_for_shell(num)
            size_arg = f"{op}{num_safe}{unit}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {size_arg}", "flag": flag}
        return None

    def _get_arg_from_relative_time_input(self, item, command_name):
        """Relative time: operator + number"""
        op = item["op_var"].get()  # Dropdown: "", "+", "-" (safe)
        num = item["num_var"].get().strip()
        
        if num:
            # SANITIZE: User can type arbitrary numbers
            num_safe = self._sanitize_for_shell(num)
            time_arg = f"{op}{num_safe}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {time_arg}", "flag": flag}
        return None

    def _get_arg_from_notable_text_input(self, item, command_name):
        """Notable text: optional NOT operator + user text"""
        not_op = item["not_var"].get()  # Dropdown: "", "!" (safe)
        value = item["var"].get().strip()
        
        if value:
            # SANITIZE: User input - CRITICAL
            value_safe = self._sanitize_for_shell(value)
            
            flag = item.get("flag", "")
            full_arg = f"{flag} {value_safe}"
            if not_op:
                full_arg = f"{not_op} {full_arg}"
            return {"arg": full_arg, "flag": flag}
        return None

    def _get_arg_from_permission_input(self, item, command_name):
        """Permission input: mode + permission string"""
        mode_str = item["mode_var"].get().split(" ")[0]  # " ", "-", "/" (safe)
        value = item["var"].get().strip()
        
        if value:
            # SANITIZE: User can type arbitrary permission strings
            value_safe = self._sanitize_for_shell(value)
            perm_arg = f"{mode_str}{value_safe}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {perm_arg}", "flag": flag}
        return None

    def _get_arg_from_date_input(self, item, command_name):
        """Date input: year-month-day with optional NOT"""
        not_op = item["not_var"].get()  # Dropdown: "", "!" (safe)
        year = item["year_var"].get()  # Dropdown (safe)
        month_str = item["month_var"].get()  # Dropdown (safe)
        day = item["day_var"].get()  # Dropdown (safe)

        if year and month_str and day:
            month = month_str.split("-")[0]
            
            # Dates from dropdowns are safe, but sanitize anyway (defense in depth)
            date_string = self._sanitize_for_shell(f"{year}-{month}-{day}")
            
            flag = item.get("flag", "")
            full_arg = f"{flag} {date_string}"
            if not_op:
                full_arg = f"{not_op} {full_arg}"
            return {"arg": full_arg, "flag": flag}
        return None

    # --- URL Validation Method ---
    def _validate_url(self, url):
        """Validate URL format."""
        if not url.strip():
            return True, ""  # Empty is ok (optional field)
        
        # Basic pattern: protocol://domain.tld/path
        pattern = r'^https?://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
        
        if not re.match(pattern, url):
            return False, "Invalid URL format. Must start with http:// or https://"
        
        return True, ""
    
    # --- URL and File with Extension Argument Getters ---
    def _get_arg_from_url(self, item, command_name):
        """URL input: protocol + user URL"""
        protocol = item["protocol_var"].get()
        url_part = item["url_var"].get().strip()
        
        if url_part:
            # Build full URL
            if url_part.startswith(("http://", "https://")):
                full_url = url_part
            else:
                full_url = f"{protocol}{url_part}"
            
            # Validate before sanitizing
            is_valid, error = self._validate_url(full_url)
            if not is_valid:
                self._show_styled_message("Invalid URL", error, is_warning=True)
                return None
            
            return {"arg": self._sanitize_for_shell(full_url), "flag": None}
        return None

    def _get_arg_from_file_w_ext(self, item, command_name):
        """File with extension: basename + extension"""
        base = item["base_var"].get().strip()
        ext = item["ext_var"].get().strip()  # Dropdown (safe)
        
        if base:
            # SANITIZE: User input filename - CRITICAL
            base_safe = self._sanitize_for_shell(base)
            # Extension is from dropdown (safe), but include it inside the quote
            full_filename = self._sanitize_for_shell(f"{base}{ext}")
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {full_filename}", "flag": flag}
            else:
                return {"arg": full_filename, "flag": None}
        return None

    def _get_arg_from_text(self, item, command_name):
        """Generic text/dropdown input"""
        if "var" not in item:
            return None
            
        value = str(item["var"].get()).strip()
        if not value:
            return None

        # For dropdowns, extract just the value before parentheses
        if item.get("type") == "dropdown" and "(" in value:
            value = value.split(" ")[0]
        
        # SANITIZE: User input - CRITICAL
        # ALWAYS sanitize, regardless of auto_quote setting
        clean_value = self._sanitize_for_shell(value)
        
        flag = item.get("flag", "")
        
        if flag:
            if item.get("prefix_flag"):
                # For flags that attach directly: -oValue
                # We need to be careful here - sanitize but keep format
                return {"arg": f"{flag}{clean_value}", "flag": flag}
            else:
                # Standard: -flag value
                return {"arg": f"{flag} {clean_value}", "flag": flag}
        else:
            # Positional argument
            return {"arg": clean_value, "flag": None}

if __name__ == "__main__":
    import platform
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lcommander.app.1.0")
        except Exception:
            pass  # Fail silently if there's any issue
    # ----------------------------------------------

    root = tk.Tk()
    app = CommandBuilderApp(root)
    root.mainloop()
