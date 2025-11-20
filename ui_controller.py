# ui_controller.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import pyperclip
import webbrowser
import re
from PIL import Image, ImageTk

from theme_manager import ThemeManager
from command_manager import CommandManager
from form_builder import FormBuilder
from command_generator import CommandGenerator
from constants import UIConstants, FileConstants
from logger_config import logger

# Optional imports
try:
    import ai_analyzer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

try:
    import settings_panel
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

try:
    import update_manager
    UPDATE_MANAGER_AVAILABLE = True
except ImportError:
    UPDATE_MANAGER_AVAILABLE = False


class UIController:
    """Main application controller"""
    
    def __init__(self, root, commands_dir, bundled_dir, logo_path):
        self.root = root
        self.root.title("Linux Command Builder")
        self.root.geometry(UIConstants.WINDOW_GEOMETRY)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Initialize managers
        self.theme = ThemeManager(root)
        self.cmd_manager = CommandManager(commands_dir, bundled_dir)
        self.form_builder = FormBuilder(
            self.theme.get_theme_config(),
            self._on_form_change
        )
        self.cmd_generator = CommandGenerator()
        
        # State
        self.current_command_info = {}
        self.sudo_var = tk.BooleanVar()
        self.logo_path = logo_path
        
        # Trackers for custom windows
        self.ai_result_window = None
        self._current_msg = None
        
        # Initialize update manager
        self.update_manager = None
        if UPDATE_MANAGER_AVAILABLE:
            self.update_manager = update_manager.UpdateManager(
                self.root,
                commands_dir,
                self.theme.get_theme_config(),
                on_update_complete=self.reload_commands
            )
            
        # Tree state
        self._tree_populated = False
        self._all_tree_items = {}
        
        # Command state caching
        self._last_command_state = None
        self._cached_command = ""
        
        # Build UI
        self._setup_ui()
        
        # Bind click handlers
        self.root.bind("<Button-1>", self._auto_close_msg, add="+")
        self.root.bind("<Button-1>", self._on_background_click, add="+")
        self.root.bind("<Escape>", self._on_escape)
        
        # Load commands
        success, errors = self.cmd_manager.load_commands()
        if not success:
            self._handle_load_failure(errors)
        else:
            self._populate_command_tree()
    
    def _setup_ui(self):
        """Build the main UI layout"""
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left sidebar
        self._setup_sidebar(main_container)
        
        # Right panel
        self._setup_right_panel(main_container)
    
    def _setup_sidebar(self, parent):
        """Create left sidebar with command tree"""
        left_frame = ttk.Frame(parent, width=UIConstants.SIDEBAR_WIDTH)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        # Logo
        if self.logo_path.exists():
            try:
                # Check file size first (prevent loading huge files)
                file_size = self.logo_path.stat().st_size
                if file_size > FileConstants.MAX_LOGO_SIZE:
                    logger.warning(f"Logo file too large: {file_size} bytes")
                    self._show_text_logo_fallback(left_frame)
                else:
                    with Image.open(self.logo_path) as original_image:
                    
                        # Validate image dimensions
                        if original_image.size[0] == 0 or original_image.size[1] == 0:
                            raise ValueError("Invalid image dimensions")
                        
                        # Multi-size icons for window
                        icon_16 = ImageTk.PhotoImage(original_image.resize((16, 16), Image.Resampling.LANCZOS))
                        icon_32 = ImageTk.PhotoImage(original_image.resize((32, 32), Image.Resampling.LANCZOS))
                        icon_48 = ImageTk.PhotoImage(original_image.resize((48, 48), Image.Resampling.LANCZOS))
                        icon_64 = ImageTk.PhotoImage(original_image.resize((64, 64), Image.Resampling.LANCZOS))
                        
                        self.icon_images = [icon_16, icon_32, icon_48, icon_64]
                        self.root.iconphoto(True, *self.icon_images)
                        
                        # Sidebar logo
                        sidebar_resized = original_image.resize((UIConstants.LOGO_SIZE, UIConstants.LOGO_SIZE), Image.Resampling.LANCZOS)
                        self.logo_img = ImageTk.PhotoImage(sidebar_resized)
                        
                        logo_label = ttk.Label(left_frame, image=self.logo_img)
                        logo_label.pack(anchor="w", padx=(10, 0), pady=(0, 0))
                    
            except FileNotFoundError:
                logger.warning(f"Logo file not found: {self.logo_path}")
                self._show_text_logo_fallback(left_frame)
            except PermissionError:
                logger.warning(f"Cannot access logo file: {self.logo_path}")
                self._show_text_logo_fallback(left_frame)
            except (ValueError, OSError) as e:
                logger.warning(f"Invalid or corrupted logo file: {e}")
                self._show_text_logo_fallback(left_frame)
            except Exception as e:
                logger.exception(f"Unexpected error loading logo:")
                self._show_text_logo_fallback(left_frame)
        else:
            self._show_text_logo_fallback(left_frame)
        
        # Title
        title = ttk.Label(left_frame, text="Commands", style="Title.TLabel")
        title.pack(pady=(0, 5), anchor="w")
        
        # Search box
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_tree())
        
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="Search...", style="Tooltip.TLabel").pack(anchor="w")
        
        # Command tree
        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        self.command_tree = ttk.Treeview(tree_container, show="tree")
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical",
                                 command=self.command_tree.yview)
        
        self.command_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.command_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Smooth scrolling
        def _on_tree_mousewheel(event):
            self.command_tree.focus_set()
            direction = -1 if event.delta > 0 else 1
            speed = 2
            self.command_tree.yview_scroll(direction * speed, "units")
            return "break"
        
        self.command_tree.bind("<MouseWheel>", _on_tree_mousewheel)
        self.command_tree.bind("<Key>", self._on_tree_keypress)
        self.command_tree.bind("<<TreeviewSelect>>", self._on_command_select)
    
    def _show_text_logo_fallback(self, parent_frame):
        """Display text when logo can't be loaded"""
        fallback_label = ttk.Label(parent_frame, text="L-COMMANDER", 
                                   style="Title.TLabel", 
                                   font=("Helvetica", 20, "bold"))
        fallback_label.pack(anchor="w", padx=(10, 0), pady=(10, 15))
    
    def _setup_right_panel(self, parent):
        """Create right panel with form and output"""
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Command title/description area
        title_frame = ttk.Frame(right_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.title_label = ttk.Label(title_frame, text="", style="Title.TLabel")
        self.title_label.pack(anchor="w")
        
        self.desc_label = ttk.Label(title_frame, 
                                    text="Select a command from the tree.",
                                    style="Description.TLabel", 
                                    wraplength=600,
                                    justify=tk.LEFT)
        self.desc_label.pack(anchor="w", pady=(5, 0))
        
        self.example_label = ttk.Label(title_frame, text="", 
                                      style="Example.TLabel",
                                      wraplength=600,
                                      justify=tk.LEFT)
        self.example_label.pack(anchor="w", pady=(5, 0))
        
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Sudo checkbox container
        self.sudo_frame = ttk.Frame(right_frame)
        self.sudo_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Scrollable form area
        form_container = ttk.Frame(right_frame)
        form_container.pack(fill=tk.BOTH, expand=True)
        
        self.form_canvas = tk.Canvas(form_container, 
                                     highlightthickness=0,
                                     bg=self.theme.BG_DARK)
        form_scrollbar = ttk.Scrollbar(form_container, 
                                      orient="vertical",
                                      command=self.form_canvas.yview)
        
        self.form_frame = ttk.Frame(self.form_canvas)
        self.form_frame.bind("<Configure>", 
                            lambda e: self.form_canvas.configure(
                                scrollregion=self.form_canvas.bbox("all")))
        
        self.form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.form_canvas.configure(yscrollcommand=form_scrollbar.set)
        
        self.form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Form mousewheel scrolling
        self.form_canvas.bind('<MouseWheel>', self._on_form_mousewheel)
        
        # Output area
        self._setup_output_area(right_frame)
    
    def _on_form_mousewheel(self, event):
        """Handle mousewheel scrolling on form"""
        scroll_region = self.form_canvas.bbox("all")
        if scroll_region:
            content_height = scroll_region[3] - scroll_region[1]
            canvas_height = self.form_canvas.winfo_height()
            if content_height > canvas_height:
                self.form_canvas.focus_set()
                self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _setup_output_area(self, parent):
        """Create command output and buttons"""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Separator(bottom_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        
        output_label = ttk.Label(bottom_frame, text="Generated Command:",
                                style="Section.TLabel")
        output_label.pack(anchor="w", pady=(0, 5))
        
        self.cmd_box = tk.Text(bottom_frame, height=4, state="disabled",
                              background=self.theme.BG_DARKER,
                              foreground=self.theme.ACCENT_GREEN,
                              insertbackground=self.theme.ACCENT_GREEN,
                              font=("Courier", 11),
                              relief="flat",
                              highlightthickness=1,
                              highlightbackground=self.theme.ACCENT_DARK)
        self.cmd_box.pack(fill=tk.X)
        
        # Buttons
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(button_frame, text="Copy Command",
                  command=self._copy_command).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Clear Form",
                  command=self._clear_form).pack(side=tk.RIGHT, padx=(0, 5))
        
        # AI Analyzer button
        if AI_AVAILABLE:
            ttk.Button(button_frame, text="Analyze with AI 🤖",
                      command=self.analyze_with_ai).pack(side=tk.RIGHT, padx=(0, 5))
        else:
            ttk.Button(button_frame, text="AI Unavailable ⚠️",
                      state="disabled",
                      style="DisabledRed.TButton").pack(side=tk.RIGHT, padx=(0, 5))
        
        # Settings button
        if SETTINGS_AVAILABLE and AI_AVAILABLE:
            ttk.Button(button_frame, text="AI Settings ⚙️",
                      command=self.open_settings).pack(side=tk.RIGHT, padx=(0, 5))
        else:
            ttk.Button(button_frame, text="Settings ⚠️",
                      state="disabled",
                      style="DisabledRed.TButton").pack(side=tk.RIGHT, padx=(0, 5))
        
        # Update manager button
        if UPDATE_MANAGER_AVAILABLE and self.update_manager:
            ttk.Button(button_frame, text="Check Updates 🔄",
                      command=self.open_update_manager).pack(side=tk.RIGHT, padx=(0, 5))
        else:
            ttk.Button(button_frame, text="Updates ⚠️",
                      state="disabled",
                      style="DisabledRed.TButton").pack(side=tk.RIGHT, padx=(0, 5))
    
    # ========== EVENT HANDLERS ==========
    def _populate_command_tree(self):
        """Fill tree with commands from manager"""
        if self._tree_populated:
            return  # Already populated
        
        for category in self.cmd_manager.get_categories():
            cat_id = self.command_tree.insert("", "end", text=category, iid=category, open=True)
            self._all_tree_items[category] = []
            
            for cmd_name in self.cmd_manager.get_commands_in_category(category):
                self.command_tree.insert(category, "end", text=cmd_name, iid=cmd_name)
                self._all_tree_items[category].append(cmd_name)
        
        self._tree_populated = True
    
    def _filter_tree(self):
        """Filter tree based on search text (optimized with detach/reattach)"""
        search_text = self.search_var.get().lower()
        
        if not self._tree_populated:
            self._populate_command_tree()
        
        if not search_text:
            # Show everything
            for category, commands in self._all_tree_items.items():
                if self.command_tree.exists(category):
                    self.command_tree.reattach(category, "", "end")
                    self.command_tree.item(category, open=True)
                for cmd in commands:
                    if self.command_tree.exists(cmd):
                        self.command_tree.reattach(cmd, category, "end")
            return
        
        # Filter results
        results = self.cmd_manager.search_commands(search_text)
        
        for category, all_commands in self._all_tree_items.items():
            matching_commands = results.get(category, [])
            
            if matching_commands:
                # Show category
                if self.command_tree.exists(category):
                    self.command_tree.reattach(category, "", "end")
                    self.command_tree.item(category, open=True)
                
                # Show/hide commands
                for cmd in all_commands:
                    if self.command_tree.exists(cmd):
                        if cmd in matching_commands:
                            self.command_tree.reattach(cmd, category, "end")
                        else:
                            self.command_tree.detach(cmd)
            else:
                # Hide entire category
                if self.command_tree.exists(category):
                    self.command_tree.detach(category)
    
    def _on_tree_keypress(self, event):
        """Handle typing in tree for search"""
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 
                           'Alt_L', 'Alt_R', 'Caps_Lock'):
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
        """Clear search on Escape"""
        self.search_var.set("")
        self.command_tree.focus_set()
    
    def _on_command_select(self, event):
        """Handle command selection from tree"""
        selected_id = self.command_tree.focus()
        if not selected_id or not self.command_tree.parent(selected_id):
            return
        
        command_name = selected_id
        category = self.command_tree.parent(selected_id)
        
        # Get command data
        cmd_data = self.cmd_manager.get_command(category, command_name)
        self.current_command_info = {
            "name": command_name,
            "data": cmd_data
        }
        
        # Update UI
        self.title_label.config(text=f"Command: {command_name}")
        self.desc_label.config(text=cmd_data.get("description", ""))
        
        example = cmd_data.get("example")
        self.example_label.config(text=f"Example: {example}" if example else "")
        
        # Clear and rebuild form
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        for widget in self.sudo_frame.winfo_children():
            widget.destroy()
        
        self.sudo_var.set(False)
        
        # Setup sudo checkbox if needed
        if cmd_data.get("requires_sudo") or cmd_data.get("sudo_optional"):
            sudo_style = "Sudo.TCheckbutton" if cmd_data.get("requires_sudo") else "TCheckbutton"
            sudo_check = ttk.Checkbutton(self.sudo_frame, 
                                        text="Run with sudo",
                                        variable=self.sudo_var,
                                        style=sudo_style,
                                        command=self._on_form_change)
            sudo_check.pack(anchor="w")
        
        # Build form
        self.form_builder.build_form(self.form_frame, cmd_data["fields"])
        
        # IMPORTANT: Trigger initial command generation after form is built
        # This ensures the command appears even if no widgets are interacted with
        self.root.after(10, self._on_form_change)
    
    def _on_form_change(self):
        """Called when any form value changes"""
        self._update_widget_states()
        self._update_command_display()
    
    def _update_widget_states(self):
        """Enable/disable widgets based on dependencies"""
        # Collect disable rules
        flags_to_disable = self._collect_flags_to_disable()
        should_disable_sudo = self._should_disable_sudo()
        
        # Apply sudo state
        self._update_sudo_state(should_disable_sudo)
        
        # Update all widgets
        is_sudo_active = self.sudo_var.get()
        for item in self.form_builder.widget_vars:
            self._update_single_widget_state(item, flags_to_disable, is_sudo_active)

    def _collect_flags_to_disable(self):
        """Collect all flags that should be disabled based on active widgets"""
        flags_to_disable = set()
        
        for item in self.form_builder.widget_vars:
            if self._is_widget_active(item) and "disables" in item:
                flags_to_disable.update(item["disables"])
        
        return flags_to_disable

    def _should_disable_sudo(self):
        """Check if any active widget disables the sudo checkbox"""
        for item in self.form_builder.widget_vars:
            if self._is_widget_active(item) and item.get("disables_sudo_checkbox"):
                return True
        return False

    def _update_sudo_state(self, should_disable):
        """Update sudo checkbox state"""
        if not self.sudo_frame.winfo_children():
            return
        
        sudo_widget = self.sudo_frame.winfo_children()[0]
        
        if should_disable:
            self.sudo_var.set(False)
            sudo_widget.config(state=tk.DISABLED)
        else:
            sudo_widget.config(state=tk.NORMAL)

    def _update_single_widget_state(self, item, flags_to_disable, is_sudo_active):
        """Update state of a single widget based on disable rules"""
        widget = item.get("widget")
        if not widget:
            return
        
        # Determine if widget should be disabled
        flag = item.get("flag", "")
        is_disabled_by_peer = flag in flags_to_disable
        is_disabled_by_sudo = is_sudo_active and item.get("disable_if_sudo")
        
        target_state = tk.DISABLED if (is_disabled_by_peer or is_disabled_by_sudo) else tk.NORMAL
        
        # Apply state based on widget type
        if item.get('type') == 'permission_grid':
            self._update_permission_grid_state(item, target_state)
        else:
            self._update_standard_widget_state(widget, target_state)

    def _update_permission_grid_state(self, item, target_state):
        """Update state of permission grid checkbuttons"""
        checkbuttons = item.get('checkbuttons', [])
        for chk in checkbuttons:
            try:
                chk.config(state=target_state)
            except tk.TclError:
                pass  # Widget doesn't support state

    def _update_standard_widget_state(self, widget, target_state):
        """Update state of standard widget (entry, combobox, etc.)"""
        try:
            if widget.winfo_class() == 'TCombobox':
                # Comboboxes use 'readonly'
                widget.config(state='readonly' if target_state == tk.NORMAL else tk.DISABLED)
            else:
                widget.config(state=target_state)
        except tk.TclError:
            pass
    
    def _is_widget_active(self, item):
        """Check if widget has a value"""
        item_type = item.get("type", "text")
        
        if item_type == "checkbox":
            return item.get("var") and item["var"].get()
        elif item_type in ["size_input", "relative_time_input"]:
            return item.get("num_var") and item["num_var"].get().strip()
        elif item_type == "date_input":
            return (item.get("year_var") and item["year_var"].get() and
                    item.get("month_var") and item["month_var"].get() and
                    item.get("day_var") and item["day_var"].get())
        elif item_type == "url":
            return item.get("url_var") and item["url_var"].get().strip()
        elif item_type == "file_w_ext":
            return item.get("base_var") and item["base_var"].get().strip()
        else:
            return item.get("var") and item["var"].get().strip()
    
    def _update_command_display(self):
        """Generate and display the command (with caching)"""
        if not self.current_command_info:
            return
        
        # Create a hashable representation of current state
        state_snapshot = self._get_form_state_hash()
        
        # Check cache
        if state_snapshot == self._last_command_state:
            return  # No changes, use cached command
        
        # Generate new command
        command = self.cmd_generator.generate_command(
            self.current_command_info["name"],
            self.form_builder.widget_vars,
            self.form_builder.permission_vars,
            self.sudo_var.get()
        )
        
        # Update cache
        self._last_command_state = state_snapshot
        self._cached_command = command
        
        # Update display
        self.cmd_box.config(state="normal")
        self.cmd_box.delete(1.0, tk.END)
        self.cmd_box.insert(1.0, command)
        self.cmd_box.config(state="disabled")
        
    def _get_form_state_hash(self):
        """Create hashable snapshot of form state for caching"""
        state_parts = [
            self.current_command_info.get("name", ""),
            str(self.sudo_var.get()),
        ]
        
        # Add all widget values
        for item in self.form_builder.widget_vars:
            item_type = item.get("type", "text")
            
            if item_type == "permission_grid":
                # Hash permission checkboxes
                for cat in ['user', 'group', 'other']:
                    for perm in ['r', 'w', 'x']:
                        val = self.form_builder.permission_vars[cat][perm].get()
                        state_parts.append(f"{cat}_{perm}_{val}")
            elif item_type in ["size_input", "relative_time_input"]:
                state_parts.append(item.get("op_var", tk.StringVar()).get())
                state_parts.append(item.get("num_var", tk.StringVar()).get())
                if "unit_var" in item:
                    state_parts.append(item["unit_var"].get())
            elif item_type == "date_input":
                state_parts.append(item.get("not_var", tk.StringVar()).get())
                state_parts.append(item.get("year_var", tk.StringVar()).get())
                state_parts.append(item.get("month_var", tk.StringVar()).get())
                state_parts.append(item.get("day_var", tk.StringVar()).get())
            elif item_type == "url":
                state_parts.append(item.get("protocol_var", tk.StringVar()).get())
                state_parts.append(item.get("url_var", tk.StringVar()).get())
            elif item_type == "file_w_ext":
                state_parts.append(item.get("base_var", tk.StringVar()).get())
                state_parts.append(item.get("ext_var", tk.StringVar()).get())
            elif item_type == "notable_text_input":
                state_parts.append(item.get("not_var", tk.StringVar()).get())
                state_parts.append(item.get("var", tk.StringVar()).get())
            elif item_type == "permission_input":
                state_parts.append(item.get("mode_var", tk.StringVar()).get())
                state_parts.append(item.get("var", tk.StringVar()).get())
            else:
                # Standard var
                if "var" in item:
                    state_parts.append(item["var"].get())
        
        # Return tuple (hashable)
        return tuple(state_parts)
    
    def _copy_command(self):
        """Copy command to clipboard"""
        command = self.cmd_box.get(1.0, tk.END).strip()
        if not command or command == self.current_command_info.get("name"):
            self._show_styled_message("No Command", 
                                     "The command is not complete yet!", 
                                     is_warning=True)
            return
        pyperclip.copy(command)
        self._show_styled_message("Copied!", 
                                 f"Copied to clipboard:\n\n{command}")
    
    def _clear_form(self):
        """Clear all form values"""
        self.form_builder.clear_form()
        self.sudo_var.set(False)
        self._on_form_change()
    
    # ========== HELPER METHODS ==========
    def _auto_close_msg(self, event):
        """Close custom message window on click"""
        if hasattr(self, '_current_msg') and self._current_msg and self._current_msg.winfo_exists():
            self._current_msg.destroy()
            self._current_msg = None
    
    def _on_background_click(self, event):
        """Clear focus when clicking background"""
        if event.widget.winfo_class() in ('TFrame', 'Frame', 'TLabel', 'Label', 
                                          'Canvas', 'TPanedwindow'):
            self.root.focus_set()
    
    def _show_styled_message(self, title, message, is_warning=False):
        """Display themed message box"""
        self._auto_close_msg(None)
        
        msg_win = tk.Toplevel(self.root)
        msg_win.title(title)
        msg_win.transient(self.root)
        msg_win.configure(bg=self.theme.BG_DARK)
        
        # Center on main window
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        
        mw, mh = UIConstants.MESSAGE_BOX_WIDTH, UIConstants.MESSAGE_BOX_HEIGHT
        msg_win.geometry(f"{mw}x{mh}+{rx + (rw//2 - mw//2)}+{ry + (rh//2 - mh//2)}")
        
        accent = self.theme.ERROR_RED if is_warning else self.theme.ACCENT_GREEN
        
        title_label = ttk.Label(msg_win, text=title, 
                               font=("Helvetica", 14, "bold"),
                               foreground=accent)
        title_label.pack(pady=(30, 15), padx=20)
        
        msg_label = ttk.Label(msg_win, text=message, 
                             wraplength=460,
                             justify="center",
                             font=("Helvetica", 11))
        msg_label.pack(pady=(0, 30), padx=20, expand=True)
        
        ok_btn = ttk.Button(msg_win, text="OK", command=msg_win.destroy)
        ok_btn.pack(pady=(0, 30), ipadx=10)
        
        ok_btn.focus_set()
        msg_win.bind("<Return>", lambda e: msg_win.destroy())
        msg_win.bind("<Escape>", lambda e: msg_win.destroy())
        
        self._current_msg = msg_win
    
    def _handle_load_failure(self, errors):
        """Handle command loading failures"""
        if not errors:
            msg = "No command files found."
        else:
            error_summary = "\n".join(errors[:3])
            if len(errors) > 3:
                error_summary += f"\n...and {len(errors) - 3} more."
            msg = f"Failed to load commands:\n\n{error_summary}"
        
        if UPDATE_MANAGER_AVAILABLE:
            msg += "\n\nWould you like to download command files now?"
            if messagebox.askyesno("Setup Required", msg):
                self.root.after(100, self.open_update_manager)
        else:
            messagebox.showerror("Setup Required", msg)
    
    # ========== FEATURE METHODS ==========
    def reload_commands(self):
        """Reload commands after update"""
        self.cmd_manager.reload()
        
        # Refresh tree
        for item in self.command_tree.get_children():
            self.command_tree.delete(item)
        self._populate_command_tree()
        
        self._show_styled_message("Success",
            f"Commands reloaded!\n\nTotal: {len(self.cmd_manager.commands_data)}")
    
    def open_settings(self):
        """Open AI settings panel"""
        if not SETTINGS_AVAILABLE:
            self._show_styled_message("Error", 
                                     "Settings module missing",
                                     is_warning=True)
            return
        settings_panel.SettingsPanel(self.root)
    
    def open_update_manager(self):
        """Open update manager window"""
        if not UPDATE_MANAGER_AVAILABLE:
            self._show_styled_message("Error",
                                     "Update manager missing",
                                     is_warning=True)
            return
        
        if self.update_manager:
            self.update_manager.open_update_window()
    
    def analyze_with_ai(self):
        """Open AI analyzer with current command"""
        if not AI_AVAILABLE:
            self._show_styled_message("Error",
                                     "AI module missing",
                                     is_warning=True)
            return
        
        command = self.cmd_box.get(1.0, tk.END).strip()
        if not command or command == self.current_command_info.get("name"):
            self._show_styled_message("Incomplete Command",
                                     "Build a more complete command first",
                                     is_warning=True)
            return
        
        # Close previous result window
        if self.ai_result_window and self.ai_result_window.winfo_exists():
            self.ai_result_window.destroy()
        
        # Show loading splash
        self._show_ai_loading_splash()
        
        # Run AI analysis
        try:
            ai_response = ai_analyzer.analyze_command(command)
        except Exception as e:
            ai_response = f"❌ **Analysis Failed**\n\n{str(e)}"
        
        # Show results
        self._show_ai_results(ai_response)
    
    def _show_ai_loading_splash(self):
        """Show loading splash with logo while AI runs"""
        # 1. Get main window coordinates
        self.root.update_idletasks()
        main_x, main_y = self.root.winfo_x(), self.root.winfo_y()
        main_w, main_h = self.root.winfo_width(), self.root.winfo_height()

        # Use constants
        splash_w, splash_h = UIConstants.SPLASH_WIDTH, UIConstants.SPLASH_HEIGHT
        splash_img = None  
        
        # 3. Load and resize logo for splash
        if self.logo_path.exists():
            try:
                with Image.open(self.logo_path) as pil_img:
                    target_w, target_h = pil_img.width // 2, pil_img.height // 2
                    resized_pil = pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    splash_img = ImageTk.PhotoImage(resized_pil)
                    splash_w, splash_h = target_w, target_h
            except Exception as e:
                logger.warning(f"Logo load error (using fallback): {e}")
                splash_img = None
                
        # 4. Calculate centered position
        s_x = main_x + (main_w // 2) - (splash_w // 2)
        s_y = main_y + (main_h // 2) - (splash_h // 2)

        # 5. Create splash window
        self.splash = tk.Toplevel(self.root)
        self.splash.overrideredirect(True)
        self.splash.geometry(f"{splash_w}x{splash_h}+{int(s_x)}+{int(s_y)}")
        
        # Green border
        self.splash.configure(background=self.theme.ACCENT_GREEN)
        
        # Dark canvas with border padding
        canvas = tk.Canvas(self.splash, width=splash_w, height=splash_h, 
                        bg=self.theme.BG_DARKER, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # 6. Display logo or fallback text
        if splash_img:
            # Keep reference to prevent garbage collection
            self.splash_img_ref = splash_img
            
            # Center logo
            canvas.create_image(splash_w//2, splash_h//2, 
                            image=splash_img, anchor="center")
            
            # Text below logo
            canvas.create_text(splash_w//2, splash_h - 20, 
                            text="Analyzing command, please wait...", 
                            fill=self.theme.FG_LIGHT, 
                            font=("Helvetica", 11))
        else:
            # Fallback: text only
            canvas.create_text(splash_w//2, splash_h//2 - 15,
                            text="L-COMMANDER",
                            fill=self.theme.ACCENT_GREEN,
                            font=("Helvetica", 24, "bold"))
            canvas.create_text(splash_w//2, splash_h//2 + 20,
                            text="Analyzing command...",
                            fill=self.theme.FG_LIGHT,
                            font=("Helvetica", 12))

        # 7. Modal behavior
        self.splash.grab_set()
        self.root.update()
    
    def _show_ai_results(self, response):
        """Display AI analysis results"""
        self.splash.grab_release()
        self.splash.destroy()
        
        # Create result window
        main_x, main_y = self.root.winfo_x(), self.root.winfo_y()
        main_w, main_h = self.root.winfo_width(), self.root.winfo_height()
        
        r_w, r_h = UIConstants.RESULT_WINDOW_WIDTH, UIConstants.RESULT_WINDOW_HEIGHT
        r_x = main_x + (main_w // 2) - (r_w // 2)
        r_y = main_y + (main_h // 2) - (r_h // 2)
        
        self.ai_result_window = tk.Toplevel(self.root)
        self.ai_result_window.title(f"AI Analysis: {self.current_command_info.get('name')}")
        self.ai_result_window.transient(self.root)
        self.ai_result_window.geometry(f"{r_w}x{r_h}+{int(r_x)}+{int(r_y)}")
        self.ai_result_window.configure(bg=self.theme.BG_DARK)
        
        result_text = scrolledtext.ScrolledText(
            self.ai_result_window,
            wrap=tk.WORD,
            font=("Helvetica", 10),
            bg=self.theme.BG_DARKER,
            fg=self.theme.FG_LIGHT,
            insertbackground=self.theme.ACCENT_GREEN,
            relief="flat"
        )
        result_text.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Insert response
        result_text.insert(tk.END, response)
        
        # Make URLs clickable
        result_text.tag_configure("hyperlink", 
                                 foreground="#4fc3f7", 
                                 underline=True)
        
        url_pattern = re.compile(r"https?://[^\s]+")
        content = result_text.get("1.0", tk.END)
        
        for match in url_pattern.finditer(content):
            start, end = match.span()
            url = match.group(0)
            start_idx = result_text.index(f"1.0 + {start} chars")
            end_idx = result_text.index(f"1.0 + {end} chars")
            
            result_text.tag_add("hyperlink", start_idx, end_idx)
            result_text.tag_bind("hyperlink", "<Button-1>", 
                               lambda e, link=url: webbrowser.open_new_tab(link))
            result_text.tag_bind("hyperlink", "<Enter>", 
                               lambda e: result_text.config(cursor="hand2"))
            result_text.tag_bind("hyperlink", "<Leave>", 
                               lambda e: result_text.config(cursor=""))
        
        result_text.config(state="disabled")
        
    def _on_closing(self):
        """Cleanup resources before closing"""
        logger.info("Application closing, cleaning up resources...")
        
        # Close AI result window if open
        try:
            if self.ai_result_window and self.ai_result_window.winfo_exists():
                self.ai_result_window.destroy()
        except Exception as e:
            logger.warning(f"Error closing AI result window: {e}")
        
        # Close custom message if open
        try:
            if hasattr(self, '_current_msg') and self._current_msg and self._current_msg.winfo_exists():
                self._current_msg.destroy()
        except Exception as e:
            logger.warning(f"Error closing message window: {e}")
        
        # Close splash if open
        try:
            if hasattr(self, 'splash') and self.splash and self.splash.winfo_exists():
                self.splash.destroy()
        except Exception as e:
            logger.warning(f"Error closing splash window: {e}")
        
        # Destroy main window
        logger.info("Cleanup complete")
        self.root.destroy()