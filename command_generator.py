# command_generator.py
import shlex
from pathlib import Path
from constants import FileConstants

# Optional validator import
try:
    import validators
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False

class CommandGenerator:
    """Generates shell commands from widget data"""
    
    # here
    def __init__(self):
        self._extractors = {
            "checkbox": self._extract_checkbox,
            "text": self._extract_text,
            "dropdown": self._extract_dropdown,
            "size_input": self._extract_size_input,
            "relative_time_input": self._extract_relative_time,
            "notable_text_input": self._extract_notable_text,
            "permission_input": self._extract_permission,
            "date_input": self._extract_date,
            "url": self._extract_url,
            "file_w_ext": self._extract_file_w_ext,
            "number_input": self._extract_number_input,
            "file_picker": self._extract_file_picker,
            "dir_picker": self._extract_dir_picker,
            "file_save_as": self._extract_file_save_as,
            "permission_grid": lambda item, cmd: None,  # Handled separately
        }

    def _extract_argument(self, item, command_name):
        """Extract command argument from widget item"""
        item_type = item.get("type", "text")
        
        extractor = self._extractors.get(item_type, self._extract_text)
        return extractor(item, command_name)
    
    
    def generate_command(self, command_name, widget_data, permission_vars, sudo_enabled):
        """
        Generate final shell command string.
        
        Args:
            command_name: str - Name of the command
            widget_data: list - List of widget item dicts
            permission_vars: dict - Permission grid state (for chmod)
            sudo_enabled: bool - Whether sudo checkbox is checked
            
        Returns:
            str - The complete shell command
        """
        prefix = "sudo " if sudo_enabled else ""
        flagged_args = []
        positional_args = []
        stderr_redirect = ""
        
        # Special handling for chmod permissions
        if command_name == "chmod" and permission_vars:
            mode = self._generate_chmod_mode(permission_vars)
            if mode != "000":
                positional_args.append(mode)
        
        # Process all widgets
        for item in widget_data:
            if not self._is_widget_active(item):
                continue
            
            arg_data = self._extract_argument(item, command_name)
            
            if arg_data:
                if arg_data.get("is_stderr_redirect"):
                    stderr_redirect = arg_data["arg"]
                elif not arg_data["flag"]:
                    positional_args.append(arg_data["arg"])
                else:
                    flagged_args.append(arg_data["arg"])
        
        # Assemble command (find is special case)
        if command_name == "find":
            parts = [f"{prefix}{command_name}"] + positional_args + flagged_args
        else:
            parts = [f"{prefix}{command_name}"] + flagged_args + positional_args
        
        final_command = " ".join(part for part in parts if part)
        final_command += stderr_redirect
        
        return final_command
    
    def _generate_chmod_mode(self, permission_vars):
        """Generate numeric chmod mode from permission grid"""
        mode = ""
        for cat in ['user', 'group', 'other']:
            val = 0
            if permission_vars[cat]['r'].get():
                val += 4
            if permission_vars[cat]['w'].get():
                val += 2
            if permission_vars[cat]['x'].get():
                val += 1
            mode += str(val)
        return mode

    def _is_widget_active(self, item):
        """Check if a widget should contribute to the command"""
        widget = item.get("widget")
        item_type = item.get("type", "text")
        
        # For permission_grid, check if any checkbutton is enabled
        if item_type == 'permission_grid':
            checkbuttons = item.get('checkbuttons', [])
            if not checkbuttons:
                return True  # No checkbuttons means assume active
            
            # Check if any checkbutton is enabled
            try:
                for chk in checkbuttons:
                    if str(chk.cget("state")) != "disabled":
                        return True
                return False  # All disabled
            except (tk.TclError, AttributeError):
                return True  # Assume active if we can't check
        
        # Check widget state (skip for widgets without state option)
        if widget:
            try:
                if str(widget.cget("state")) == "disabled":
                    return False
            except (tk.TclError, AttributeError):
                # Widget doesn't have state option (like Frame) - continue checking
                pass
        
        # Check if widget has a value
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

    
    def _sanitize_for_shell(self, value):
            """Safely escape value for shell use"""
            if not value:
                return value
            
            str_value = str(value)
            
            # Prevent DoS via long inputs
            if len(str_value) > FileConstants.MAX_INPUT_LENGTH:
                return shlex.quote(str_value[:FileConstants.MAX_INPUT_LENGTH])
            
            return shlex.quote(str_value)
    
    # Individual extractor methods...
    def _extract_checkbox(self, item, command_name):
        if not item["var"].get():
            return None
        
        flag = item.get("flag", "")
        if flag == "redirect_stderr":
            return {"arg": " 2>/dev/null", "flag": flag, "is_stderr_redirect": True}
        
        return {"arg": flag, "flag": flag}
    
    def _extract_text(self, item, command_name):
        if "var" not in item:
            return None
        
        value = str(item["var"].get()).strip()
        if not value:
            return None
        
        # For dropdowns, extract value before parentheses
        if item.get("type") == "dropdown" and "(" in value:
            value = value.split(" ")[0]
        
        clean_value = self._sanitize_for_shell(value)
        flag = item.get("flag", "")
        
        if flag:
            if item.get("prefix_flag"):
                return {"arg": f"{flag}{clean_value}", "flag": flag}
            else:
                return {"arg": f"{flag} {clean_value}", "flag": flag}
        else:
            return {"arg": clean_value, "flag": None}
    
    def _extract_size_input(self, item, command_name):
        """Extract size argument (e.g., +100M, -5k)"""
        op = item["op_var"].get()  # "", "+", or "-"
        num = item["num_var"].get().strip()
        unit = item["unit_var"].get()  # "c", "k", "M", "G"
        
        if num and unit:
            num_safe = self._sanitize_for_shell(num)
            size_arg = f"{op}{num_safe}{unit}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {size_arg}", "flag": flag}
        return None
    
    def _extract_relative_time(self, item, command_name):
        """Extract relative time argument (e.g., +7, -30)"""
        op = item["op_var"].get()  # "", "+", or "-"
        num = item["num_var"].get().strip()
        
        if num:
            num_safe = self._sanitize_for_shell(num)
            time_arg = f"{op}{num_safe}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {time_arg}", "flag": flag}
        return None
    
    def _extract_notable_text(self, item, command_name):
        """Extract text with optional NOT operator (e.g., ! -name "*.txt")"""
        not_op = item["not_var"].get()  # "" or "!"
        value = item["var"].get().strip()
        
        if value:
            value_safe = self._sanitize_for_shell(value)
            
            flag = item.get("flag", "")
            full_arg = f"{flag} {value_safe}"
            if not_op:
                full_arg = f"{not_op} {full_arg}"
            return {"arg": full_arg, "flag": flag}
        return None
    
    def _extract_permission(self, item, command_name):
        """Extract permission argument (e.g., -perm -644, /755)"""
        mode_str = item["mode_var"].get().split(" ")[0]  # " ", "-", or "/"
        value = item["var"].get().strip()
        
        if value:
            value_safe = self._sanitize_for_shell(value)
            perm_arg = f"{mode_str}{value_safe}"
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {perm_arg}", "flag": flag}
        return None
    
    def _extract_date(self, item, command_name):
        """Extract date argument (e.g., -newermt 2024-01-15)"""
        not_op = item["not_var"].get()  # "" or "!"
        year = item["year_var"].get()
        month_str = item["month_var"].get()  # "01-Jan" format
        day = item["day_var"].get()
        
        if year and month_str and day:
            month = month_str.split("-")[0]  # Extract "01" from "01-Jan"
            date_string = self._sanitize_for_shell(f"{year}-{month}-{day}")
            
            flag = item.get("flag", "")
            full_arg = f"{flag} {date_string}"
            if not_op:
                full_arg = f"{not_op} {full_arg}"
            return {"arg": full_arg, "flag": flag}
        return None
    
    def _extract_url(self, item, command_name):
        """Extract URL argument (e.g., https://example.com/file.tar.gz)"""
        protocol = item["protocol_var"].get()
        url_part = item["url_var"].get().strip()
        
        if not url_part:
            return None
        
        # Build full URL
        if url_part.startswith(("http://", "https://")):
            full_url = url_part
        else:
            full_url = f"{protocol}{url_part}"
        
        # Validate URL format
        if not self._validate_url(full_url):
            # Invalid URL - skip it (validation styling already handled in FormBuilder)
            return None
        
        # Valid URL - return sanitized
        return {"arg": self._sanitize_for_shell(full_url), "flag": None}
    
    def _extract_file_w_ext(self, item, command_name):
        """Extract filename with extension (e.g., backup.tar.gz)"""
        base = item["base_var"].get().strip()
        ext = item["ext_var"].get().strip()  # From dropdown
        
        if base:
            # Combine basename and extension, then sanitize as a unit
            full_filename = self._sanitize_for_shell(f"{base}{ext}")
            
            flag = item.get("flag", "")
            if flag:
                return {"arg": f"{flag} {full_filename}", "flag": flag}
            else:
                return {"arg": full_filename, "flag": None}
        return None
    
    def _extract_number_input(self, item, command_name):
        """Extract numeric input (e.g., -n 10, -depth 3)"""
        if "var" not in item:
            return None
        
        value = item["var"].get().strip()
        if not value:
            return None
        
        # Numbers are safe (validated by widget), but sanitize anyway
        clean_value = self._sanitize_for_shell(value)
        
        flag = item.get("flag", "")
        if flag:
            return {"arg": f"{flag} {clean_value}", "flag": flag}
        else:
            return {"arg": clean_value, "flag": None}
    
    def _extract_file_picker(self, item, command_name):
        """Extract file path from file picker widget"""
        if "var" not in item:
            return None
        
        path = item["var"].get().strip()
        if not path:
            return None
        
        # Sanitize path
        clean_path = self._sanitize_for_shell(path)
        
        flag = item.get("flag", "")
        if flag:
            return {"arg": f"{flag} {clean_path}", "flag": flag}
        else:
            return {"arg": clean_path, "flag": None}
    
    def _extract_dir_picker(self, item, command_name):
        """Extract directory path from directory picker widget"""
        return self._extract_file_picker(item, command_name)
    
    def _extract_file_save_as(self, item, command_name):
        """Extract save path from save-as dialog"""
        return self._extract_file_picker(item, command_name)
    
    def _extract_dropdown(self, item, command_name):
        """Extract value from dropdown widget"""
        return self._extract_text(item, command_name)
    
    # Validation helper methods
    def _validate_url(self, url):
        """Validate URL using validators library."""
        if not url.strip():
            return True
        
        if VALIDATORS_AVAILABLE:
            return validators.url(url) is True
        else:
            # Fallback to manual validation if validators not installed
            return self._validate_url_manual(url)
        
    def _validate_url_manual(self, url):
        """
        Fallback URL validation without validators library.
        Basic validation - not as comprehensive as validators package.
        """
        import re
        
        # Empty URLs are allowed
        if not url.strip():
            return True
        
        # No whitespace allowed
        if any(c in url for c in [' ', '\n', '\t', '\r']):
            return False
        
        # Must start with http:// or https://
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Basic URL pattern
        # Matches: protocol://domain.tld/path?query#fragment
        pattern = r'^https?://[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*(\.[a-zA-Z]{2,})(:[0-9]{1,5})?(/.*)?$'
        
        if not re.match(pattern, url, re.IGNORECASE):
            return False
        
        # Validate port number if present
        if '://' in url:
            try:
                # Extract everything after protocol
                after_protocol = url.split('://')[1]
                # Get domain/port part (before any path)
                domain_part = after_protocol.split('/')[0]
                
                # Check if port exists
                if ':' in domain_part:
                    port_str = domain_part.split(':')[1]
                    port = int(port_str)
                    
                    # Valid port range
                    if not (1 <= port <= 65535):
                        return False
            except (ValueError, IndexError):
                # Malformed port
                return False
        
        return True

    def _validate_path_chars(self, path):
        """
        Check for invalid filesystem characters.
        
        Args:
            path: str - Path to validate
            
        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        # Invalid on Windows/Linux/Mac
        invalid_chars = '<>:"|?*'
        
        for char in invalid_chars:
            if char in path:
                return False, f"Invalid character: '{char}'"
        
        # Check for invalid Windows reserved names
        invalid_names = ['CON', 'PRN', 'AUX', 'NUL', 
                        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 
                        'COM6', 'COM7', 'COM8', 'COM9',
                        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
                        'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        from pathlib import Path
        name_only = Path(path).name.upper().split('.')[0]
        if name_only in invalid_names:
            return False, f"'{name_only}' is a reserved system name"
        
        return True, ""