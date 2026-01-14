#!/usr/bin/env python3
"""Simple test without GUI imports."""

import ast
import inspect

print("1. Checking app.py for show_today method...")
with open('src/getmoredone/app.py', 'r') as f:
    app_content = f.read()

# Parse the AST
tree = ast.parse(app_content)

# Find the GetMoreDoneApp class
found_class = False
found_method = False
found_button = False

for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'GetMoreDoneApp':
        found_class = True
        print(f"   ✓ Found GetMoreDoneApp class")

        # Check for show_today method
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == 'show_today':
                found_method = True
                print(f"   ✓ Found show_today method at line {item.lineno}")

# Check for button configuration
if 'command=self.show_today' in app_content:
    found_button = True
    print("   ✓ Button wired to self.show_today")

if not found_class:
    print("   ✗ GetMoreDoneApp class not found!")
if not found_method:
    print("   ✗ show_today method not found in class!")
if not found_button:
    print("   ✗ Button not wired to show_today!")

print("\n2. Checking today.py file exists...")
import os
if os.path.exists('src/getmoredone/screens/today.py'):
    print("   ✓ today.py exists")
    size = os.path.getsize('src/getmoredone/screens/today.py')
    print(f"   File size: {size} bytes")
else:
    print("   ✗ today.py NOT found!")

print("\n3. Checking today.py for TodayScreen class...")
with open('src/getmoredone/screens/today.py', 'r') as f:
    today_content = f.read()

tree = ast.parse(today_content)
found_today_class = False

for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'TodayScreen':
        found_today_class = True
        print(f"   ✓ Found TodayScreen class at line {node.lineno}")

        # Check for __init__ method
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                # Get parameter names
                args = [arg.arg for arg in item.args.args]
                print(f"   __init__ parameters: {args}")

if not found_today_class:
    print("   ✗ TodayScreen class not found!")

print("\n4. Syntax check...")
try:
    compile(today_content, 'today.py', 'exec')
    compile(app_content, 'app.py', 'exec')
    print("   ✓ Both files compile without syntax errors")
except SyntaxError as e:
    print(f"   ✗ Syntax error: {e}")

if found_class and found_method and found_button and found_today_class:
    print("\n✓ ALL CHECKS PASSED")
    print("\nThe code appears correct. Possible issues:")
    print("  1. Application needs to be restarted")
    print("  2. Silent exception when clicking (check terminal output)")
    print("  3. Old .pyc files cached (try: find . -name '*.pyc' -delete)")
else:
    print("\n✗ SOME CHECKS FAILED - see above")
