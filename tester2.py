import unittest
import tkinter as tk

import command_generator
print(f"--- LOADING command_generator FROM: {command_generator.__file__} ---")

from command_generator import CommandGenerator
from unittest.mock import Mock, MagicMock

class TestCommandGenerator(unittest.TestCase):
    
    def setUp(self):
        """Set up a fresh generator and a root Tk instance for StringVars"""
        self.generator = CommandGenerator()
        self.root = tk.Tk()
    
    def tearDown(self):
        """Destroy the root Tk instance"""
        self.root.destroy()
    
    # --- _sanitize_for_shell Tests ---

    def test_sanitize_simple(self):
        """Test basic sanitization"""
        result = self.generator._sanitize_for_shell("test.txt")
        # FIX: shlex.quote does not quote simple strings
        self.assertEqual(result, "test.txt")
    
    def test_sanitize_with_spaces(self):
        """Test sanitization of string with spaces"""
        result = self.generator._sanitize_for_shell("my test file.txt")
        # This test was correct, as shlex.quote *does* quote strings with spaces
        self.assertEqual(result, "'my test file.txt'")
        
    def test_sanitize_injection_attempt(self):
        """Test sanitization of shell injection attempt"""
        result = self.generator._sanitize_for_shell("file; rm -rf /")
        # This test was correct, shlex.quote *does* quote this
        self.assertEqual(result, "'file; rm -rf /'")
        
    def test_sanitize_long_string(self):
        """Test truncation of very long strings"""
        long_str = "A" * 9000
        result = self.generator._sanitize_for_shell(long_str)
        # FIX: A simple string is not quoted, so length is 8000
        self.assertEqual(len(result), 8000)
        self.assertTrue(result.startswith("AAAAAAAA"))

    # --- _extract_text Tests (Happy and Unhappy) ---

    def test_extract_text_with_flag(self):
        """Test basic text extraction with flag"""
        var = tk.StringVar(value="test.txt")
        item = {"type": "text", "flag": "-f", "var": var}
        result = self.generator._extract_text(item, "find")
        
        # FIX: 'test.txt' is not quoted
        self.assertEqual(result["arg"], "-f test.txt")
        self.assertEqual(result["flag"], "-f")

    def test_extract_text_with_spaces(self):
        """Test text extraction with spaces"""
        var = tk.StringVar(value="my file.txt")
        item = {"type": "text", "flag": "-name", "var": var}
        result = self.generator._extract_text(item, "find")
        # This test was correct
        self.assertEqual(result["arg"], "-name 'my file.txt'")

    def test_extract_text_empty(self):
        """Test empty text input"""
        var = tk.StringVar(value="")
        item = {"type": "text", "flag": "-f", "var": var}
        result = self.generator._extract_text(item, "find")
        self.assertIsNone(result)

    def test_extract_text_empty_spaces(self):
        """Test text input with only spaces"""
        var = tk.StringVar(value="   ")
        item = {"type": "text", "flag": "-f", "var": var}
        result = self.generator._extract_text(item, "find")
        self.assertIsNone(result)

    def test_extract_text_no_flag(self):
        """Test text extraction for a positional argument"""
        var = tk.StringVar(value="/home/user")
        item = {"type": "text", "flag": "", "var": var}
        result = self.generator._extract_text(item, "find")
        # FIX: Simple string is not quoted
        self.assertEqual(result["arg"], "/home/user")
        self.assertIsNone(result["flag"])
        
    def test_extract_text_prefix_flag(self):
        """Test text extraction with a prefix flag (no space)"""
        var = tk.StringVar(value="10")
        item = {"type": "text", "flag": "-I", "var": var, "prefix_flag": True}
        result = self.generator._extract_text(item, "grep")
        # FIX: Simple number is not quoted
        self.assertEqual(result["arg"], "-I10")

    # --- _extract_checkbox Tests ---

    def test_extract_checkbox_true(self):
        """Test checkbox when True"""
        var = tk.BooleanVar(value=True)
        item = {"type": "checkbox", "flag": "-l", "var": var}
        result = self.generator._extract_checkbox(item, "ls")
        self.assertEqual(result["arg"], "-l")
        self.assertEqual(result["flag"], "-l")
        
    def test_extract_checkbox_false(self):
        """Test checkbox when False"""
        var = tk.BooleanVar(value=False)
        item = {"type": "checkbox", "flag": "-l", "var": var}
        result = self.generator._extract_checkbox(item, "ls")
        self.assertIsNone(result)
        
    def test_extract_checkbox_stderr_redirect(self):
        """Test special stderr redirect checkbox"""
        var = tk.BooleanVar(value=True)
        item = {"type": "checkbox", "flag": "redirect_stderr", "var": var}
        result = self.generator._extract_checkbox(item, "find")
        self.assertEqual(result["arg"], " 2>/dev/null")
        self.assertTrue(result["is_stderr_redirect"])

    # --- _extract_size_input Tests ---
    
    def test_extract_size_input_happy(self):
        """Test full size input"""
        item = {
            "flag": "-size",
            "op_var": tk.StringVar(value="+"),
            "num_var": tk.StringVar(value="100"),
            "unit_var": tk.StringVar(value="M")
        }
        result = self.generator._extract_size_input(item, "find")
        self.assertEqual(result["arg"], "-size +100M")

    def test_extract_size_input_no_op(self):
        """Test size input with no operator"""
        item = {
            "flag": "-size",
            "op_var": tk.StringVar(value=""),
            "num_var": tk.StringVar(value="50"),
            "unit_var": tk.StringVar(value="k")
        }
        result = self.generator._extract_size_input(item, "find")
        self.assertEqual(result["arg"], "-size 50k")

    def test_extract_size_input_empty_num(self):
        """Test size input with empty number"""
        item = {
            "flag": "-size",
            "op_var": tk.StringVar(value="+"),
            "num_var": tk.StringVar(value=""),
            "unit_var": tk.StringVar(value="M")
        }
        result = self.generator._extract_size_input(item, "find")
        self.assertIsNone(result)

    # --- _generate_chmod_mode Tests ---
    
    def create_permission_vars(self, user, group, other):
        """Helper to create permission_vars dict"""
        def get_bool(val, char):
            return tk.BooleanVar(value=(char in val))
            
        return {
            'user': {'r': get_bool(user, 'r'), 'w': get_bool(user, 'w'), 'x': get_bool(user, 'x')},
            'group': {'r': get_bool(group, 'r'), 'w': get_bool(group, 'w'), 'x': get_bool(group, 'x')},
            'other': {'r': get_bool(other, 'r'), 'w': get_bool(other, 'w'), 'x': get_bool(other, 'x')}
        }

    def test_chmod_mode_754(self):
        """Test chmod 754 (rwx, r-x, r--)"""
        permission_vars = self.create_permission_vars("rwx", "rx", "r")
        mode = self.generator._generate_chmod_mode(permission_vars)
        self.assertEqual(mode, "754")
        
    def test_chmod_mode_000(self):
        """Test chmod 000 (---, ---, ---)"""
        permission_vars = self.create_permission_vars("", "", "")
        mode = self.generator._generate_chmod_mode(permission_vars)
        self.assertEqual(mode, "000")

    def test_chmod_mode_777(self):
        """Test chmod 777 (rwx, rwx, rwx)"""
        permission_vars = self.create_permission_vars("rwx", "rwx", "rwx")
        mode = self.generator._generate_chmod_mode(permission_vars)
        self.assertEqual(mode, "777")
        
    def test_chmod_mode_640(self):
        """Test chmod 640 (rw-, r--, ---)"""
        permission_vars = self.create_permission_vars("rw", "r", "")
        mode = self.generator._generate_chmod_mode(permission_vars)
        self.assertEqual(mode, "640")

    # --- _is_widget_active Tests ---
    
    def test_is_widget_active_disabled_widget(self):
        """Test that a disabled widget is not active"""
        # Mock a tkinter widget
        mock_widget = MagicMock(spec=tk.Entry)
        mock_widget.cget.return_value = "disabled"
        
        item = {"widget": mock_widget, "var": tk.StringVar(value="test")}
        self.assertFalse(self.generator._is_widget_active(item))
        
    def test_is_widget_active_enabled_widget(self):
        """Test that an enabled widget with value is active"""
        mock_widget = MagicMock(spec=tk.Entry)
        mock_widget.cget.return_value = "normal"
        
        item = {"widget": mock_widget, "var": tk.StringVar(value="test")}
        self.assertTrue(self.generator._is_widget_active(item))

    def test_is_widget_active_checkbox_true(self):
        """Test active checkbox"""
        item = {"type": "checkbox", "var": tk.BooleanVar(value=True)}
        self.assertTrue(self.generator._is_widget_active(item))
        
    def test_is_widget_active_checkbox_false(self):
        """Test inactive checkbox"""
        item = {"type": "checkbox", "var": tk.BooleanVar(value=False)}
        self.assertFalse(self.generator._is_widget_active(item))

    def test_is_widget_active_text_empty(self):
        """Test inactive text widget"""
        item = {"type": "text", "var": tk.StringVar(value="")}
        self.assertFalse(self.generator._is_widget_active(item))

    # --- generate_command (Full Integration) Tests ---
    
    def test_generate_command_find(self):
        """Test 'find' command special case"""
        widget_data = [
            {"type": "text", "flag": "", "var": tk.StringVar(value="/var/log")}, # Positional
            {"type": "text", "flag": "-name", "var": tk.StringVar(value="*.log")}, # Flagged
            {"type": "checkbox", "flag": "redirect_stderr", "var": tk.BooleanVar(value=True)}
        ]
        command = self.generator.generate_command("find", widget_data, {}, False)
        # FIX: /var/log is simple, but *.log is quoted
        self.assertEqual(command, "find /var/log -name '*.log' 2>/dev/null")

    def test_generate_command_tar(self):
        """Test a normal command (tar)"""
        widget_data = [
            {"type": "text", "flag": "", "var": tk.StringVar(value="archive.tar.gz")}, # Positional
            {"type": "text", "flag": "-f", "var": tk.StringVar(value="file.txt")}, # Flagged
            {"type": "checkbox", "flag": "-c", "var": tk.BooleanVar(value=True)}, # Flagged
            {"type": "checkbox", "flag": "-z", "var": tk.BooleanVar(value=True)} # Flagged
        ]
        command = self.generator.generate_command("tar", widget_data, {}, False)
        # FIX: None of these simple strings are quoted
        self.assertEqual(command, "tar -f file.txt -c -z archive.tar.gz")
        
    def test_generate_command_with_sudo(self):
        """Test sudo prefix"""
        widget_data = [
            {"type": "text", "flag": "", "var": tk.StringVar(value="nginx")}
        ]
        command = self.generator.generate_command("systemctl", widget_data, {}, True)
        # FIX: 'nginx' is not quoted
        self.assertEqual(command, "sudo systemctl nginx")

    def test_generate_command_chmod_full(self):
        """Test chmod command with permissions and path"""
        widget_data = [
            {"type": "dir_picker", "flag": "", "var": tk.StringVar(value="/my/dir")} # Positional
        ]
        permission_vars = self.create_permission_vars("rwx", "rx", "") # 750
        command = self.generator.generate_command("chmod", widget_data, permission_vars, False)
        # FIX: '/my/dir' is not quoted
        self.assertEqual(command, "chmod 750 /my/dir")
        
    def test_generate_command_chmod_no_path(self):
        """Test chmod with only permissions"""
        widget_data = []
        permission_vars = self.create_permission_vars("rwx", "rwx", "rwx") # 777
        command = self.generator.generate_command("chmod", widget_data, permission_vars, False)
        self.assertEqual(command, "chmod 777")
        
    def test_generate_command_inactive_widgets(self):
        """Test that inactive (disabled) widgets are skipped"""
        mock_widget = MagicMock(spec=tk.Entry)
        mock_widget.cget.return_value = "disabled"
        
        widget_data = [
            {"type": "text", "flag": "-f", "var": tk.StringVar(value="active.txt")},
            {"type": "text", "flag": "-d", "var": tk.StringVar(value="disabled.txt"), "widget": mock_widget},
            {"type": "checkbox", "flag": "-l", "var": tk.BooleanVar(value=False)}
        ]
        command = self.generator.generate_command("ls", widget_data, {}, False)
        # FIX: 'active.txt' is not quoted
        self.assertEqual(command, "ls -f active.txt")


if __name__ == '__main__':
    unittest.main()