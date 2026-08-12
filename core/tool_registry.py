"""
Tool registry — the single source of truth for what Phin can *do*.
Add a new capability by: writing the function in tools/, then registering
its schema + handler here. Both LLM providers consume this same list.
"""
from tools import computer, files, browser, code_editor, ui_control
from core.memory import Memory

TOOLS = [
    {
        "name": "open_app",
        "description": "Open an application on the PC by name (e.g. 'chrome', 'notepad', 'spotify').",
        "input_schema": {
            "type": "object",
            "properties": {"app_name": {"type": "string"}},
            "required": ["app_name"],
        },
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen and save it. Does NOT analyze the content — use describe_screen if the user wants to know what's actually shown.",
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string", "description": "short label for the file name"}},
        },
    },
    {
        "name": "describe_screen",
        "description": "Look at the current screen and answer a question about what's visible (e.g. 'what error is showing', 'what app is open', 'read the text in this window'). Use this instead of take_screenshot whenever the user wants to know WHAT is on screen.",
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string", "description": "what to look for or ask about the screen"}},
        },
    },
    {
        "name": "type_text",
        "description": "Type text at the current cursor focus (e.g. into a text field the user already clicked into).",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "press_hotkey",
        "description": "Press a keyboard shortcut, e.g. keys=['ctrl','s'] to save.",
        "input_schema": {
            "type": "object",
            "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
            "required": ["keys"],
        },
    },
    {
        "name": "close_active_window",
        "description": "Close the currently focused/active window.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_text_file",
        "description": "Create a plain text file on the desktop.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "create_word_document",
        "description": "Create a Word (.docx) document on the desktop with a title and body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["filename", "body"],
        },
    },
    {
        "name": "create_pdf",
        "description": "Create a PDF file on the desktop with a title and body text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["filename", "body"],
        },
    },
    {
        "name": "remember",
        "description": "Store a durable fact about the user for future conversations, e.g. key='preferred_ide', value='VS Code'.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Look up a previously stored fact about the user by key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },

    # --- Browser control ---
    {
        "name": "open_url",
        "description": "Open a URL/website in a brand new browser tab.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "search_web",
        "description": "Open a new tab and search the web for a query (e.g. 'search for best pizza near me').",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "new_tab",
        "description": "Open a new blank tab in the currently focused browser window.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "close_tab",
        "description": "Close the currently active browser tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "next_tab",
        "description": "Switch to the next browser tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "previous_tab",
        "description": "Switch to the previous browser tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "reopen_closed_tab",
        "description": "Reopen the most recently closed browser tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "go_to_tab_number",
        "description": "Jump directly to a specific tab by its position number (1-8) in the browser's tab bar.",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    },
    {
        "name": "navigate_current_tab",
        "description": "Navigate the CURRENTLY OPEN/focused tab to a new URL (reuses the tab instead of opening a new one).",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },

    # --- Code / file editing ---
    {
        "name": "read_file",
        "description": "Read the contents of a code or text file from disk by its full path, so it can be discussed or rewritten.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Overwrite (or create) a file at an exact path with new content. Use for 'rewrite this file' or 'save this code' requests. Always read_file first if the file already exists, so you know what you're replacing.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "find_replace_in_file",
        "description": "Make a small, targeted edit to a file by replacing one exact snippet with another, leaving the rest of the file untouched. Prefer this over write_file for small changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "find": {"type": "string"},
                "replace": {"type": "string"},
            },
            "required": ["path", "find", "replace"],
        },
    },
    {
        "name": "append_to_file",
        "description": "Append content to the end of a file without touching existing content.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List the files and folders inside a directory, so Phin knows what's there before reading or editing something.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },

    # --- Phin's own UI ---
    {
        "name": "open_dashboard",
        "description": "Open Phin's own main interface/dashboard window on screen — use when the user asks to 'open your dashboard', 'show yourself', 'pull up your UI', or similar.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "close_dashboard",
        "description": "Close Phin's dashboard window, collapsing it back down to the small orb.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def dispatch(name: str, tool_input: dict, memory: Memory) -> str:
    try:
        if name == "open_app":
            return computer.open_app(tool_input["app_name"])
        if name == "take_screenshot":
            return computer.take_screenshot(tool_input.get("label", "screenshot"))
        if name == "describe_screen":
            return computer.describe_screen(tool_input.get("question", "What's on the screen right now?"))
        if name == "type_text":
            return computer.type_text(tool_input["text"])
        if name == "press_hotkey":
            return computer.press_hotkey(*tool_input["keys"])
        if name == "close_active_window":
            return computer.close_active_window()
        if name == "create_text_file":
            return files.create_text_file(tool_input["filename"], tool_input["content"])
        if name == "create_word_document":
            return files.create_word_document(
                tool_input["filename"], tool_input.get("title", ""), tool_input["body"]
            )
        if name == "create_pdf":
            return files.create_pdf(
                tool_input["filename"], tool_input.get("title", ""), tool_input["body"]
            )
        if name == "remember":
            memory.remember(tool_input["key"], tool_input["value"])
            return f"Remembered: {tool_input['key']} = {tool_input['value']}"
        if name == "recall":
            val = memory.recall(tool_input["key"])
            return val if val else f"No memory found for '{tool_input['key']}'."

        # Browser
        if name == "open_url":
            return browser.open_url(tool_input["url"])
        if name == "search_web":
            return browser.search_web(tool_input["query"])
        if name == "new_tab":
            return browser.new_tab()
        if name == "close_tab":
            return browser.close_tab()
        if name == "next_tab":
            return browser.next_tab()
        if name == "previous_tab":
            return browser.previous_tab()
        if name == "reopen_closed_tab":
            return browser.reopen_closed_tab()
        if name == "go_to_tab_number":
            return browser.go_to_tab_number(tool_input["n"])
        if name == "navigate_current_tab":
            return browser.focus_address_bar_and_go(tool_input["url"])

        # Code / file editing
        if name == "read_file":
            return code_editor.read_file(tool_input["path"])
        if name == "write_file":
            return code_editor.write_file(tool_input["path"], tool_input["content"])
        if name == "find_replace_in_file":
            return code_editor.find_replace_in_file(
                tool_input["path"], tool_input["find"], tool_input["replace"]
            )
        if name == "append_to_file":
            return code_editor.append_to_file(tool_input["path"], tool_input["content"])
        if name == "list_directory":
            return code_editor.list_directory(tool_input["path"])

        # Phin's own UI
        if name == "open_dashboard":
            return ui_control.open_dashboard()
        if name == "close_dashboard":
            return ui_control.close_dashboard()

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool '{name}' failed: {e}"
