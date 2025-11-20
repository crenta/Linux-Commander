# test_integration.py
"""Integration tests for the full application"""
import unittest
import tkinter as tk
from pathlib import Path
from command_manager import CommandManager
from form_builder import FormBuilder
from command_generator import CommandGenerator

class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.test_dir = Path(__file__).parent / "test_commands"
        self.test_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        """Clean up"""
        self.root.destroy()
        # Clean up test files if needed
        
    def test_full_find_command_workflow(self):
        """Test complete workflow: load JSON → build form → generate command"""
        # Create test JSON
        test_json = self.test_dir / "test.json"
        test_json.write_text('''
        {
            "Test": {
                "find": {
                    "description": "Test find command",
                    "fields": [
                        {"type": "text", "label": "Path", "flag": ""},
                        {"type": "text", "label": "Name", "flag": "-name"}
                    ]
                }
            }
        }
        ''')
        
        # Load commands
        manager = CommandManager(self.test_dir, self.test_dir)
        success, errors = manager.load_commands()
        self.assertTrue(success)
        
        # Generate command
        generator = CommandGenerator()
        widget_data = [
            {"type": "text", "flag": "", "var": tk.StringVar(value="/home")},
            {"type": "text", "flag": "-name", "var": tk.StringVar(value="*.txt")}
        ]
        
        command = generator.generate_command("find", widget_data, {}, False)
        self.assertIn("/home", command)
        self.assertIn("-name", command)
        self.assertIn("*.txt", command)

if __name__ == '__main__':
    unittest.main()