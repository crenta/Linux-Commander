# command_manager.py
import json
from pathlib import Path
from tkinter import messagebox

class CommandManager:
    """Loads and manages command definitions from JSON files"""
    
    def __init__(self, commands_dir, bundled_dir):
        self.commands_dir = Path(commands_dir)
        self.bundled_dir = Path(bundled_dir)
        self.commands_data = {}
    
    def load_commands(self):
        """
        Load commands from disk.
        Returns: (success: bool, error_messages: list)
        """
        # Determine which directory to load from
        if self.commands_dir.exists() and any(self.commands_dir.glob("*.json")):
            load_from = self.commands_dir
        elif self.bundled_dir.exists() and any(self.bundled_dir.glob("*.json")):
            load_from = self.bundled_dir
        else:
            return False, ["No command files found"]
        
        # Load all JSON files
        load_errors = []
        for json_file in load_from.glob("*.json"):
            if json_file.name.startswith("."):
                continue
            
            try:
                # Check file size before loading (prevent DoS)
                file_size = json_file.stat().st_size
                MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB limit
                if file_size > MAX_JSON_SIZE:
                    load_errors.append(f"{json_file.name}: File too large ({file_size} bytes)")
                    continue
                
                with open(json_file, 'r', encoding='utf-8', newline='') as f:
                    data = json.load(f)
                
                # Validate JSON structure
                if not isinstance(data, dict):
                    load_errors.append(f"{json_file.name}: Root must be a dictionary")
                    continue
                
                # Validate each category
                for category, commands in data.items():
                    if not isinstance(commands, dict):
                        load_errors.append(f"{json_file.name}: Category '{category}' must be a dictionary")
                        continue
                    
                    # Validate each command
                    for cmd_name, cmd_data in commands.items():
                        if not isinstance(cmd_data, dict):
                            load_errors.append(f"{json_file.name}: Command '{cmd_name}' must be a dictionary")
                            continue
                        
                        # Ensure required fields exist
                        if "fields" not in cmd_data:
                            load_errors.append(f"{json_file.name}: Command '{cmd_name}' missing 'fields'")
                            continue
                        
                        if not isinstance(cmd_data["fields"], list):
                            load_errors.append(f"{json_file.name}: Command '{cmd_name}' fields must be a list")
                            continue
                
                # If validation passed, add to commands
                self.commands_data.update(data)
                
            except json.JSONDecodeError as e:
                load_errors.append(f"{json_file.name}: Invalid JSON at line {e.lineno}")
            except PermissionError as e:
                load_errors.append(f"{json_file.name}: Permission denied")
            except Exception as e:
                load_errors.append(f"{json_file.name}: {str(e)}")
        
        success = len(self.commands_data) > 0
        return success, load_errors
    
    def get_all_commands(self):
        """Returns the complete commands dictionary"""
        return self.commands_data
    
    def get_command(self, category, command_name):
        """Get a specific command definition"""
        return self.commands_data.get(category, {}).get(command_name)
    
    def get_categories(self):
        """Returns sorted list of category names"""
        return sorted(self.commands_data.keys())
    
    def get_commands_in_category(self, category):
        """Returns sorted list of command names in a category"""
        return sorted(self.commands_data.get(category, {}).keys())
    
    def search_commands(self, search_text):
        """
        Search commands by name, description, or example.
        Returns: dict of {category: [matching_command_names]}
        """
        search_lower = search_text.lower()
        results = {}
        
        for category_name in self.commands_data:
            commands = self.commands_data[category_name]
            
            # Check if category matches
            is_category_match = search_lower in category_name.lower()
            
            # Find matching commands
            matching = []
            for cmd_name, cmd_data in commands.items():
                if (search_lower in cmd_name.lower() or
                    search_lower in cmd_data.get("description", "").lower() or
                    search_lower in cmd_data.get("example", "").lower()):
                    matching.append(cmd_name)
            
            # Include category if it matches or has matching commands
            if is_category_match or matching:
                results[category_name] = sorted(matching) if matching else sorted(commands.keys())
        
        return results
    
    def reload(self):
        """Clear and reload all commands"""
        self.commands_data.clear()
        return self.load_commands()