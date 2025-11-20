import unittest
import tkinter as tk
from command_generator import CommandGenerator

class TestCommandGenerator(unittest.TestCase):
    
    def setUp(self):
        self.generator = CommandGenerator()
        self.root = tk.Tk()  # Needed for StringVar
    
    def tearDown(self):
        self.root.destroy()
    
    def test_extract_text_with_flag(self):
        """Test basic text extraction with flag"""
        var = tk.StringVar(value="test.txt")
        item = {
            "type": "text",
            "flag": "-f",
            "var": var
        }
        
        result = self.generator._extract_text(item, "find")
        
        # FIX: shlex.quote does not quote simple, safe strings.
        self.assertEqual(result["arg"], "-f test.txt")
        self.assertEqual(result["flag"], "-f")
    
    def test_extract_text_with_special_chars(self):
        """Test shell injection prevention"""
        var = tk.StringVar(value="test'; rm -rf /")
        item = {
            "type": "text",
            "flag": "-name",
            "var": var
        }
        
        result = self.generator._extract_text(item, "find")
        
        # FIX: Update the assertion to expect the *correctly escaped*
        # string produced by shlex.quote.
        self.assertEqual(result["arg"], "-name 'test'\"'\"'; rm -rf /'")
    
    def test_extract_size_input(self):
        """Test size input extraction"""
        op_var = tk.StringVar(value="+")
        num_var = tk.StringVar(value="100")
        unit_var = tk.StringVar(value="M")
        
        item = {
            "type": "size_input",
            "flag": "-size",
            "op_var": op_var,
            "num_var": num_var,
            "unit_var": unit_var
        }
        
        result = self.generator._extract_size_input(item, "find")
        
        # This test was already correct
        self.assertEqual(result["arg"], "-size +100M")
    
    def test_extract_date_input(self):
        """Test date input extraction"""
        not_var = tk.StringVar(value="")
        year_var = tk.StringVar(value="2024")
        month_var = tk.StringVar(value="01-Jan")
        day_var = tk.StringVar(value="15")
        
        item = {
            "type": "date_input",
            "flag": "-newermt",
            "not_var": not_var,
            "year_var": year_var,
            "month_var": month_var,
            "day_var": day_var
        }
        
        result = self.generator._extract_date(item, "find")
        
        # This test was already correct
        self.assertEqual(result["arg"], "-newermt 2024-01-15")
    
    def test_extract_url(self):
        """Test URL extraction"""
        protocol_var = tk.StringVar(value="https://")
        url_var = tk.StringVar(value="example.com/file.tar.gz")
        
        item = {
            "type": "url",
            "protocol_var": protocol_var,
            "url_var": url_var
        }
        
        result = self.generator._extract_url(item, "wget")
        
        # This test was already correct
        self.assertIn("https://example.com/file.tar.gz", result["arg"])
    
    def test_extract_checkbox_stderr_redirect(self):
        """Test special stderr redirect checkbox"""
        var = tk.BooleanVar(value=True)
        
        item = {
            "type": "checkbox",
            "flag": "redirect_stderr",
            "var": var
        }
        
        result = self.generator._extract_checkbox(item, "find")
        
        # This test was already correct
        self.assertEqual(result["arg"], " 2>/dev/null")
        self.assertTrue(result["is_stderr_redirect"])
    
    def test_generate_chmod_mode(self):
        """Test chmod numeric mode generation"""
        permission_vars = {
            'user': {
                'r': tk.BooleanVar(value=True),
                'w': tk.BooleanVar(value=True),
                'x': tk.BooleanVar(value=True)
            },
            'group': {
                'r': tk.BooleanVar(value=True),
                'w': tk.BooleanVar(value=False),
                'x': tk.BooleanVar(value=True)
            },
            'other': {
                'r': tk.BooleanVar(value=True),
                'w': tk.BooleanVar(value=False),
                'x': tk.BooleanVar(value=False)
            }
        }
        
        mode = self.generator._generate_chmod_mode(permission_vars)
        
        # This test was already correct
        self.assertEqual(mode, "754")
    
    def test_sanitize_long_input(self):
        """Test DoS prevention via length limit"""
        long_string = "A" * 10000
        
        result = self.generator._sanitize_for_shell(long_string)
        
        # FIX: The unquoted string will be exactly 8000 chars
        self.assertEqual(len(result), 8000)

if __name__ == '__main__':
    unittest.main()