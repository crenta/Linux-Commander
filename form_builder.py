# form_builder.py
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import calendar
import datetime
import re
from constants import FileConstants, ValidationConstants
from logger_config import logger

# Optional validator import
try:
    import validators
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False

class FormBuilder:
    """Builds UI widgets from command definitions"""
    
    def __init__(self, theme_config, on_change_callback):
        self.theme = theme_config
        self.on_change = on_change_callback
        self.widget_vars = []
        self.permission_vars = {}
    
    def build_form(self, parent_frame, field_definitions):
        """
        Build form widgets from field definitions.
        
        Args:
            parent_frame: ttk.Frame - Parent container
            field_definitions: list - Field specs from JSON
            
        Returns:
            list - Widget data items
        """
        self.widget_vars.clear()
        
        for field_data in field_definitions:
            frame = ttk.Frame(parent_frame)
            frame.pack(fill=tk.X, pady=4)
            
            widget_frame = ttk.Frame(frame)
            widget_frame.pack(fill=tk.X)
            
            widget_data = field_data.copy()
            if 'type' not in widget_data:
                widget_data['type'] = 'text'
            
            # Build the appropriate widget
            self._build_widget(widget_frame, widget_data)
            
            # Add tooltip if present
            if "tooltip" in field_data:
                tooltip_label = ttk.Label(frame, text=field_data["tooltip"], 
                                         style="Tooltip.TLabel")
                tooltip_label.pack(fill=tk.X, padx=(25, 10), pady=(0, 0))
        
        return self.widget_vars
    
    def _build_widget(self, parent_frame, widget_data):
        """Dispatch to appropriate widget builder"""
        widget_type = widget_data['type']
        
        builders = {
            "permission_grid": self._build_permission_grid,
            "checkbox": self._build_checkbox,
            "dropdown": self._build_dropdown,
            "text": self._build_text,
            "size_input": self._build_size_input,
            "relative_time_input": self._build_relative_time_input,
            "notable_text_input": self._build_notable_text_input,
            "permission_input": self._build_permission_input,
            "date_input": self._build_date_input,
            "url": self._build_url,
            "file_w_ext": self._build_file_w_ext,
            "file_picker": self._build_file_picker,
            "dir_picker": self._build_dir_picker,
            "file_save_as": self._build_file_save_as,
            "number_input": self._build_number_input,
        }
        
        builder = builders.get(widget_type, self._build_text)
        builder(parent_frame, widget_data)
    
    # ========== WIDGET BUILDERS ==========
    def _build_permission_grid(self, parent_frame, widget_data):
        """Build chmod permission grid (User/Group/Other x R/W/X)"""
        try:
            # Validate widget_data
            if not isinstance(widget_data, dict):
                raise ValueError("widget_data must be a dictionary")
            
            # Initialize permission variables
            self.permission_vars = {
                'user': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()},
                'group': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()},
                'other': {'r': tk.BooleanVar(), 'w': tk.BooleanVar(), 'x': tk.BooleanVar()}
            }
            
            main_frame = ttk.Frame(parent_frame)
            main_frame.pack(fill=tk.X)
            
            categories = {'User': 'user', 'Group': 'group', 'Other': 'other'}
            permissions = {'Read': 'r', 'Write': 'w', 'Execute': 'x'}
            
            # Store all checkbuttons for enable/disable
            all_checkbuttons = []
            
            for cat_label, cat_key in categories.items():
                labelframe = ttk.LabelFrame(main_frame, text=cat_label)
                labelframe.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                
                for perm_label, perm_key in permissions.items():
                    chk = ttk.Checkbutton(
                        labelframe, 
                        text=perm_label,
                        variable=self.permission_vars[cat_key][perm_key],
                        command=self.on_change
                    )
                    chk.pack(anchor="w", padx=10)
                    all_checkbuttons.append(chk)
            
            # Store reference in widget_data
            widget_data.update({
                "permission_vars": self.permission_vars,
                "widget": main_frame,
                "checkbuttons": all_checkbuttons
            })
            self.widget_vars.append(widget_data)
            
        except tk.TclError as e:
            logger.error(f"Error creating permission grid widget: {e}")
            # Create fallback simple text
            ttk.Label(parent_frame, 
                    text=f"{widget_data.get('label', 'Permissions')}: (Widget creation failed)",
                    foreground="red").pack()
        except (ValueError, KeyError) as e:
            logger.error(f"Configuration error in permission grid: {e}")
            ttk.Label(parent_frame, 
                    text=f"{widget_data.get('label', 'Permissions')}: (Configuration error)",
                    foreground="red").pack()
        except Exception as e:
            logger.exception(f"Unexpected error in _build_permission_grid:")
            ttk.Label(parent_frame, 
                    text=f"{widget_data.get('label', 'Permissions')}: (Error)",
                    foreground="red").pack()
    
    def _build_checkbox(self, parent_frame, widget_data):
        """Build a simple checkbox"""
        var = tk.BooleanVar()
        chk = ttk.Checkbutton(
            parent_frame, 
            text=widget_data["label"],
            variable=var, 
            command=self.on_change
        )
        chk.pack(anchor="w")
        
        widget_data.update({"var": var, "widget": chk})
        self.widget_vars.append(widget_data)
    
    def _build_dropdown(self, parent_frame, widget_data):
        """Build a dropdown/combobox"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        var = tk.StringVar()
        combo = ttk.Combobox(
            parent_frame, 
            textvariable=var,
            values=widget_data.get("options", []),
            state="readonly",
            width=30
        )
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        widget_data.update({"var": var, "widget": combo})
        self.widget_vars.append(widget_data)
    
    def _build_text(self, parent_frame, widget_data):
        """Build a text entry widget with validation"""
        # Container to prevent expansion
        container = ttk.Frame(parent_frame)
        container.pack(fill=tk.X)
        
        label = ttk.Label(container, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        # Right side container for entry + feedback
        right_container = ttk.Frame(container)
        right_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        var = tk.StringVar()
        entry = ttk.Entry(right_container, textvariable=var)
        entry.pack(fill=tk.X)
        
        # Add validation feedback label (hidden by default)
        feedback_label = ttk.Label(right_container, text="", style="Tooltip.TLabel")
        # DON'T pack it yet - only pack when needed
        
        # Debounce timer to prevent lag
        validation_timer = [None]
        
        def validate_on_change(*args):
            if validation_timer[0]:
                container.after_cancel(validation_timer[0])
            
            value = var.get()
            max_len = widget_data.get("max_length", FileConstants.DEFAULT_MAX_TEXT_LENGTH)

            
            if len(value) > max_len:
                feedback_label.config(
                    text=f"⚠️ Too long ({len(value)}/{max_len})", 
                    foreground=self.theme["ERROR_RED"]
                )
                entry.config(style="Invalid.TEntry")
                # Show the feedback label
                if not feedback_label.winfo_ismapped():
                    feedback_label.pack(fill=tk.X, anchor="w")
            else:
                feedback_label.config(text="")
                entry.config(style="TEntry")
                # Hide the feedback label
                if feedback_label.winfo_ismapped():
                    feedback_label.pack_forget()
            
            validation_timer[0] = container.after(300, self.on_change)
        
        var.trace_add("write", validate_on_change)
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)
    
    def _build_size_input(self, parent_frame, widget_data):
        """Build size input (operator + number + unit) - e.g., +100M"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        size_frame = ttk.Frame(parent_frame)
        size_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Operator dropdown (+, -, or exact)
        op_var = tk.StringVar()
        op_combo = ttk.Combobox(
            size_frame, 
            textvariable=op_var,
            values=["", "+", "-"],
            state="readonly",
            width=3
        )
        op_combo.pack(side=tk.LEFT)
        op_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        # Number entry
        num_var = tk.StringVar()
        num_var.trace_add("write", lambda n, i, m: self.on_change())
        num_entry = ttk.Entry(size_frame, textvariable=num_var, width=10)
        num_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Unit dropdown (bytes, KB, MB, GB)
        unit_var = tk.StringVar()
        unit_options = widget_data.get("options", ["c", "k", "M", "G"])
        unit_combo = ttk.Combobox(
            size_frame,
            textvariable=unit_var,
            values=unit_options,
            state="readonly",
            width=5
        )
        unit_combo.pack(side=tk.LEFT, padx=(5, 0))
        unit_combo.set(unit_options[0] if unit_options else "")
        unit_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        widget_data.update({
            "op_var": op_var,
            "num_var": num_var,
            "unit_var": unit_var,
            "widget": num_entry
        })
        self.widget_vars.append(widget_data)
    
    def _build_relative_time_input(self, parent_frame, widget_data):
        """Build relative time input (operator + number) - e.g., -7 days"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        time_frame = ttk.Frame(parent_frame)
        time_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Operator dropdown (+, -, or exact)
        op_var = tk.StringVar()
        op_combo = ttk.Combobox(
            time_frame,
            textvariable=op_var,
            values=["", "+", "-"],
            state="readonly",
            width=3
        )
        op_combo.pack(side=tk.LEFT)
        op_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        # Number entry
        num_var = tk.StringVar()
        num_var.trace_add("write", lambda n, i, m: self.on_change())
        num_entry = ttk.Entry(time_frame, textvariable=num_var, width=10)
        num_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        widget_data.update({
            "op_var": op_var,
            "num_var": num_var,
            "widget": num_entry
        })
        self.widget_vars.append(widget_data)
    
    def _build_notable_text_input(self, parent_frame, widget_data):
        """Build text input with NOT operator - e.g., ! -name "*.txt" """
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        not_frame = ttk.Frame(parent_frame)
        not_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # NOT operator dropdown
        not_var = tk.StringVar()
        not_combo = ttk.Combobox(
            not_frame,
            textvariable=not_var,
            values=["", "!"],
            state="readonly",
            width=3
        )
        not_combo.pack(side=tk.LEFT)
        not_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        # Text entry
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self.on_change())
        entry = ttk.Entry(not_frame, textvariable=var, width=20)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        widget_data.update({
            "not_var": not_var,
            "var": var,
            "widget": entry
        })
        self.widget_vars.append(widget_data)
    
    def _build_permission_input(self, parent_frame, widget_data):
        """Build permission input (mode + permission string) - e.g., -644"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        perm_frame = ttk.Frame(parent_frame)
        perm_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Mode dropdown (exact, at least, any of)
        mode_var = tk.StringVar()
        mode_options = [" (exact)", "- (at least)", "/ (any of)"]
        mode_combo = ttk.Combobox(
            perm_frame,
            textvariable=mode_var,
            values=mode_options,
            state="readonly",
            width=12
        )
        mode_combo.pack(side=tk.LEFT)
        mode_combo.set(mode_options[0])
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        # Permission entry
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self.on_change())
        entry = ttk.Entry(perm_frame, textvariable=var, width=15)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        widget_data.update({
            "mode_var": mode_var,
            "var": var,
            "widget": entry
        })
        self.widget_vars.append(widget_data)

    def _build_date_input(self, parent_frame, widget_data):
        """Build date input (NOT + Year/Month/Day dropdowns)"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        date_frame = ttk.Frame(parent_frame)
        date_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # NOT operator
        not_var = tk.StringVar()
        not_combo = ttk.Combobox(
            date_frame,
            textvariable=not_var,
            values=["", "!"],
            state="readonly",
            width=3
        )
        not_combo.pack(side=tk.LEFT)
        
        # Year dropdown
        year_var = tk.StringVar()
        current_year = datetime.date.today().year
        
        # Handle special "current" keyword or convert to int
        raw_min = widget_data.get("min_year", current_year - 50)
        raw_max = widget_data.get("max_year", current_year + 5)
        
        # Convert min_year, handling "current" keyword
        if isinstance(raw_min, str) and raw_min.lower() == "current":
            min_year = current_year
        elif isinstance(raw_min, str):
            try:
                min_year = int(raw_min)
            except ValueError:
                min_year = current_year - 50
        else:
            min_year = int(raw_min)
        
        # Convert max_year, handling "current" keyword
        if isinstance(raw_max, str) and raw_max.lower() == "current":
            max_year = current_year
        elif isinstance(raw_max, str):
            try:
                max_year = int(raw_max)
            except ValueError:
                max_year = current_year + 5
        else:
            max_year = int(raw_max)
        
        year_list = [""] + list(range(max_year, min_year - 1, -1))
        year_combo = ttk.Combobox(
            date_frame,
            textvariable=year_var,
            values=year_list,
            state="readonly",
            width=6
        )
        year_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Month dropdown
        month_var = tk.StringVar()
        month_list = ["", "01-Jan", "02-Feb", "03-Mar", "04-Apr", "05-May", "06-Jun",
                    "07-Jul", "08-Aug", "09-Sep", "10-Oct", "11-Nov", "12-Dec"]
        month_combo = ttk.Combobox(
            date_frame,
            textvariable=month_var,
            values=month_list,
            state="readonly",
            width=8
        )
        month_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Day dropdown
        day_var = tk.StringVar()
        day_list = [""] + [f"{i:02d}" for i in range(1, 32)]
        day_combo = ttk.Combobox(
            date_frame,
            textvariable=day_var,
            values=day_list,
            state="readonly",
            width=4
        )
        day_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Bind events to update days based on selected month/year
        def update_days(*args):
            self._update_days_for_date_widget(year_var, month_var, day_var, day_combo)
        
        year_combo.bind("<<ComboboxSelected>>", update_days)
        month_combo.bind("<<ComboboxSelected>>", update_days)
        day_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        not_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        widget_data.update({
            "not_var": not_var,
            "year_var": year_var,
            "month_var": month_var,
            "day_var": day_var,
            "widget": year_combo,
            "day_combo_widget": day_combo
        })
        self.widget_vars.append(widget_data)
    
    def _update_days_for_date_widget(self, year_var, month_var, day_var, day_combo):
        """Helper to update day dropdown based on selected month/year"""
        try:
            year_str = year_var.get()
            month_str = month_var.get()
            
            if year_str and month_str:
                year = int(year_str)
                month = int(month_str.split("-")[0])  # "02-Feb" -> 02
                
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
        
        self.on_change()
    
    def _build_url(self, parent_frame, widget_data):
        """Build URL input (protocol dropdown + URL entry)"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        url_frame = ttk.Frame(parent_frame)
        url_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Protocol dropdown
        protocol_var = tk.StringVar(value="https://")
        protocol_combo = ttk.Combobox(
            url_frame,
            textvariable=protocol_var,
            values=["https://", "http://"],
            width=8,
            state="readonly"
        )
        protocol_combo.pack(side=tk.LEFT)
        protocol_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        # URL entry
        url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Real-time validation function
        def validate_on_change(*args):
            url_part = url_var.get().strip()
            protocol = protocol_var.get()
            
            if not url_part:
                # Empty field - normal style
                url_entry.configure(style='TEntry')
            else:
                # Build full URL and validate
                if url_part.startswith(("http://", "https://")):
                    full_url = url_part
                else:
                    full_url = f"{protocol}{url_part}"
                
                # Validate URL
                if VALIDATORS_AVAILABLE:
                    is_valid = validators.url(full_url) is True
                else:
                    # Fallback validation
                    is_valid = self._validate_url_manual(full_url)
                
                if is_valid:
                    url_entry.configure(style='TEntry')
                else:
                    url_entry.configure(style='Invalid.TEntry')
            
            # Trigger command regeneration
            self.on_change()
        
        # Bind validation to variable changes
        url_var.trace_add("write", validate_on_change)
        protocol_var.trace_add("write", validate_on_change)
        
        widget_data.update({
            "protocol_var": protocol_var,
            "url_var": url_var,
            "widget": url_entry
        })
        self.widget_vars.append(widget_data)
        
    def _validate_url_manual(self, url):
        """
        Fallback URL validation without validators library.
        Basic validation - not as comprehensive as validators package.
        """
        if not url.strip():
            return True
        
        # No whitespace allowed
        if any(c in url for c in [' ', '\n', '\t', '\r']):
            return False
        
        # Must start with http:// or https://
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Basic URL pattern
        import re
        pattern = r'^https?://[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*(\.[a-zA-Z]{2,})(:[0-9]{1,5})?(/.*)?$'
        
        if not re.match(pattern, url, re.IGNORECASE):
            return False
        
        # Validate port number if present
        if '://' in url:
            try:
                after_protocol = url.split('://')[1]
                domain_part = after_protocol.split('/')[0]
                
                if ':' in domain_part:
                    port_str = domain_part.split(':')[1]
                    port = int(port_str)
                    
                    if not (1 <= port <= 65535):
                        return False
            except (ValueError, IndexError):
                return False
        
        return True
    
    def _is_valid_path_syntax(self, path):
        """
        Check if path has valid syntax (not if it exists).
        Attempts to find a balance for both Windows and Unix.
        Allows shell wildcards like * and ?.
        
        Returns:
            (bool, str): (is_valid, error_message)
        """
        import re

        # 1. Block the only universally invalid character
        if '\0' in path:
            return False, "Invalid NUL character"

        # 2. Check for empty/whitespace-only paths
        # (The caller should handle this, but good to double-check)
        if not path or path.isspace():
            return False, "" # Empty is not "invalid", just empty

        # 3. Block Windows-specific invalid characters that are NOT
        #    shell wildcards. We allow *, ?, <, >, | because shlex.quote()
        #    will handle them for the command.
        #
        #    The main culprits are ':' (in the wrong place) and '"'.
        if '"' in path:
            return False, "Path cannot contain double quotes"
            
        if ':' in path:
            # A colon is ONLY allowed as the second character (e.g., "C:")
            # and must be followed by a separator.
            colon_indices = [i for i, char in enumerate(path) if char == ':']
            for i in colon_indices:
                if i != 1:
                    # This is a colon *not* in the 'C:' position (e.g., "my:file.txt")
                    return False, f"Invalid character ':'"
                if i == 1:
                    if len(path) > 2 and path[2] not in ('/', '\\'):
                        # This is "C:file" (invalid) instead of "C:\file" or "C:/file"
                        return False, r"Drive letter must be followed by \ or /"
                    if len(path) == 2 and path[0].isalpha():
                        # This is just "C:" which is fine
                        pass
                    elif not path[0].isalpha():
                         return False, "Drive letter must be a letter"

        # 4. Check for Windows Reserved Names (as the *final* part of the path)
        # We need to get the filename/directory name, not the whole path.
        
        # Replace both types of slashes with a standard one
        normalized_path = path.replace('\\', '/')
        # Get the last component
        last_component = normalized_path.split('/')[-1]
        
        # Get the "name" part before any extension
        name_only = last_component.split('.')[0].upper()
        
        invalid_names = [
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
            'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        if name_only in invalid_names:
            return False, f"'{last_component}' is a reserved system name"

        # 5. Check for consecutive slashes
        if '///' in path or r'\\\\' in path: # check both
             return False, "Too many consecutive separators"

        # If it passed all checks, it's valid
        return True, ""
    
    def _build_file_w_ext(self, parent_frame, widget_data):
        """Build file with extension (basename + extension dropdown)"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        file_frame = ttk.Frame(parent_frame)
        file_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Base filename entry
        base_var = tk.StringVar()
        base_var.trace_add("write", lambda n, i, m: self.on_change())
        base_entry = ttk.Entry(file_frame, textvariable=base_var)
        base_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Extension dropdown
        ext_var = tk.StringVar()
        options = widget_data.get("options", [])
        if options:
            ext_combo = ttk.Combobox(
                file_frame,
                textvariable=ext_var,
                values=options,
                state="readonly",
                width=10
            )
            ext_combo.pack(side=tk.LEFT)
            ext_combo.set(options[0])
            ext_combo.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        
        widget_data.update({
            "base_var": base_var,
            "ext_var": ext_var,
            "widget": base_entry
        })
        self.widget_vars.append(widget_data)
    
    def _build_file_picker(self, parent_frame, widget_data):
        """Build file picker (entry + browse button)"""
        # Main container
        container = ttk.Frame(parent_frame)
        container.pack(fill=tk.X)

        label = ttk.Label(container, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        # Right side for entry + button + feedback
        right_container = ttk.Frame(container)
        right_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        var = tk.StringVar()
        
        picker_frame = ttk.Frame(right_container)
        picker_frame.pack(fill=tk.X)
        
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_file():
            path = filedialog.askopenfilename()
            if path:
                var.set(Path(path).as_posix())
        
        button = ttk.Button(picker_frame, text="Browse...", command=browse_file)
        button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Feedback label (hidden by default)
        feedback_label = ttk.Label(right_container, text="", 
                                style="Tooltip.TLabel", 
                                foreground=self.theme["ERROR_RED"])
        
        def validate_path_syntax(*args):
            """Validate path syntax (not existence)"""
            path = var.get()
            
            if not path:
                entry.configure(style='TEntry')
                # Hide feedback
                if feedback_label.winfo_ismapped():
                    feedback_label.pack_forget()
            else:
                is_valid, error_message = self._is_valid_path_syntax(path)
                
                if is_valid:
                    entry.configure(style='TEntry')
                    # Hide feedback
                    if feedback_label.winfo_ismapped():
                        feedback_label.pack_forget()
                else:
                    entry.configure(style='Invalid.TEntry')
                    feedback_label.config(text=f"⚠️ {error_message}")
                    # Show feedback
                    if not feedback_label.winfo_ismapped():
                        feedback_label.pack(fill=tk.X, anchor="w")
            
            self.on_change()
        
        var.trace_add("write", validate_path_syntax)
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)
    
    def _build_dir_picker(self, parent_frame, widget_data):
        """Build directory picker (entry + browse button)"""
        # Main container
        container = ttk.Frame(parent_frame)
        container.pack(fill=tk.X)

        label = ttk.Label(container, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        # Right side for entry + button + feedback
        right_container = ttk.Frame(container)
        right_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        var = tk.StringVar()
        
        picker_frame = ttk.Frame(right_container)
        picker_frame.pack(fill=tk.X)
        
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_dir():
            path = filedialog.askdirectory()
            if path:
                var.set(Path(path).as_posix())
        
        button = ttk.Button(picker_frame, text="Browse...", command=browse_dir)
        button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Feedback label (hidden by default)
        feedback_label = ttk.Label(right_container, text="", 
                                style="Tooltip.TLabel", 
                                foreground=self.theme["ERROR_RED"])
        
        def validate_path_syntax(*args):
            """Validate path syntax (not existence)"""
            path = var.get()
            
            if not path:
                entry.configure(style='TEntry')
                if feedback_label.winfo_ismapped():
                    feedback_label.pack_forget()
            else:
                is_valid, error_message = self._is_valid_path_syntax(path)
                
                if is_valid:
                    entry.configure(style='TEntry')
                    if feedback_label.winfo_ismapped():
                        feedback_label.pack_forget()
                else:
                    entry.configure(style='Invalid.TEntry')
                    feedback_label.config(text=f"⚠️ {error_message}")
                    if not feedback_label.winfo_ismapped():
                        feedback_label.pack(fill=tk.X, anchor="w")
            
            self.on_change()
        
        var.trace_add("write", validate_path_syntax)
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)
    
    def _build_file_save_as(self, parent_frame, widget_data):
        """Build save-as file picker (entry + save button)"""
        # Main container
        container = ttk.Frame(parent_frame)
        container.pack(fill=tk.X)
        
        label = ttk.Label(container, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        # Right side for entry + button + feedback
        right_container = ttk.Frame(container)
        right_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        var = tk.StringVar()
        
        picker_frame = ttk.Frame(right_container)
        picker_frame.pack(fill=tk.X)
        
        entry = ttk.Entry(picker_frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def save_as():
            path = filedialog.asksaveasfilename()
            if path:
                var.set(Path(path).as_posix())
        
        button = ttk.Button(picker_frame, text="Save As...", command=save_as)
        button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Feedback label (hidden by default)
        feedback_label = ttk.Label(right_container, text="", 
                                style="Tooltip.TLabel", 
                                foreground=self.theme["ERROR_RED"])
        
        def validate_path_syntax(*args):
            """Validate path syntax (not existence)"""
            path = var.get()
            
            if not path:
                entry.configure(style='TEntry')
                if feedback_label.winfo_ismapped():
                    feedback_label.pack_forget()
            else:
                is_valid, error_message = self._is_valid_path_syntax(path)
                
                if is_valid:
                    entry.configure(style='TEntry')
                    if feedback_label.winfo_ismapped():
                        feedback_label.pack_forget()
                else:
                    entry.configure(style='Invalid.TEntry')
                    feedback_label.config(text=f"⚠️ {error_message}")
                    if not feedback_label.winfo_ismapped():
                        feedback_label.pack(fill=tk.X, anchor="w")
            
            self.on_change()
        
        var.trace_add("write", validate_path_syntax)
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)
    
    def _build_number_input(self, parent_frame, widget_data):
        """Build number-only input with validation"""
        label = ttk.Label(parent_frame, text=f"{widget_data['label']}:")
        label.pack(side=tk.LEFT, anchor="w")
        
        var = tk.StringVar()
        var.trace_add("write", lambda n, i, m: self.on_change())
        
        # Get bounds from widget_data
        min_val = widget_data.get("min", 0)
        max_val = widget_data.get("max", 999999)
        
        # Validation function
        def validate_number(P):
            if P == "":
                return True
            if not P.isdigit():
                return False
            try:
                num = int(P)
                return min_val <= num <= max_val
            except ValueError:
                return False
        
        vcmd = (parent_frame.register(validate_number), '%P')
        entry = ttk.Entry(
            parent_frame,
            textvariable=var,
            validate="key",
            validatecommand=vcmd
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        widget_data.update({"var": var, "widget": entry})
        self.widget_vars.append(widget_data)
    
    # ========== CLEARING METHODS ==========
    
    def clear_form(self):
        """Reset all widget values"""
        for item in self.widget_vars:
            self._clear_widget(item)
        
        if self.permission_vars:
            for category in self.permission_vars.values():
                for perm_var in category.values():
                    perm_var.set(False)
    
    def _clear_widget(self, item):
        """Clear a single widget's value"""
        item_type = item.get("type", "text")
        
        clearers = {
            "checkbox": self._clear_checkbox,
            "text": self._clear_text,
            "dropdown": self._clear_text,
            "size_input": self._clear_size_input,
            "relative_time_input": self._clear_relative_time_input,
            "notable_text_input": self._clear_notable_text_input,
            "permission_input": self._clear_permission_input,
            "date_input": self._clear_date_input,
            "url": self._clear_url,
            "file_w_ext": self._clear_file_w_ext,
            "file_picker": self._clear_text,
            "dir_picker": self._clear_text,
            "file_save_as": self._clear_text,
            "number_input": self._clear_text,
            "permission_grid": lambda item: None,
        }
        
        clearer = clearers.get(item_type, self._clear_text)
        clearer(item)
    
    def _clear_checkbox(self, item):
        item["var"].set(False)
    
    def _clear_text(self, item):
        if "var" in item:
            item["var"].set("")
    
    def _clear_size_input(self, item):
        item["op_var"].set("")
        item["num_var"].set("")
        options = item.get("options", [])
        item["unit_var"].set(options[0] if options else "")
    
    def _clear_relative_time_input(self, item):
        item["op_var"].set("")
        item["num_var"].set("")
    
    def _clear_notable_text_input(self, item):
        item["not_var"].set("")
        item["var"].set("")
    
    def _clear_permission_input(self, item):
        item["mode_var"].set(" (exact)")
        item["var"].set("")
    
    def _clear_date_input(self, item):
        item["not_var"].set("")
        item["year_var"].set("")
        item["month_var"].set("")
        item["day_var"].set("")
        default_days = [""] + [f"{i:02d}" for i in range(1, 32)]
        item["day_combo_widget"]['values'] = default_days
    
    def _clear_url(self, item):
        item["protocol_var"].set("https://")
        item["url_var"].set("")
    
    def _clear_file_w_ext(self, item):
        item["base_var"].set("")
        if item.get("ext_var"):
            options = item.get("options", [])
            item["ext_var"].set(options[0] if options else "")