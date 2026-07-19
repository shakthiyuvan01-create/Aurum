"""tools/computer_control.py - Mouse, keyboard, screenshot, app control, screen info"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

NAME = "computer_control"
DESCRIPTION = "Control computer: mouse, keyboard, screenshot, open apps, file management, browser automation"
CATEGORY = "builtin"
ICON = "🖥️"

INPUTS = [
    {"name":"action","type":"str","required":True,"placeholder":"mouse_move|mouse_click|keyboard_type|screenshot|open_app|list_windows|run_command|file_manager"},
    {"name":"x","type":"int","placeholder":"X coordinate"},
    {"name":"y","type":"int","placeholder":"Y coordinate"},
    {"name":"text","type":"str","placeholder":"Text to type or command"},
    {"name":"path","type":"str","placeholder":"File/App path"},
    {"name":"button","type":"str","placeholder":"left|right|middle"},
    {"name":"key","type":"str","placeholder":"enter|tab|esc|up|down"},
]

def run(action="",x=0,y=0,text="",path="",button="left",key="",**kw):
    a=action.strip().lower()
    if a=="mouse_move": return _mouse_move(x,y)
    if a=="mouse_click": return _mouse_click(x,y,button)
    if a=="keyboard_type": return _keyboard_type(text)
    if a=="keyboard_press": return _keyboard_press(key)
    if a=="screenshot": return _screenshot(path)
    if a=="open_app": return _open_app(path or text)
    if a=="list_windows": return _list_windows()
    if a=="run_command": return _run_command(text)
    if a=="file_manager": return _file_manager(text,path)
    if a=="get_screen_size": return _get_screen_size()
    return {"error":f"Unknown: {action}"}

def _mouse_move(x,y):
    try:
        import pyautogui; pyautogui.moveTo(x,y); return {"result":f"Moved to ({x},{y})"}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}

def _mouse_click(x,y,button):
    try:
        import pyautogui
        if x or y: pyautogui.click(x,y,button=button)
        else: pyautogui.click(button=button)
        return {"result":f"Clicked {button}"}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}

def _keyboard_type(text):
    try:
        import pyautogui; pyautogui.typewrite(text,interval=0.05); return {"result":f"Typed {len(text)} chars"}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}

def _keyboard_press(key):
    try:
        import pyautogui; pyautogui.press(key); return {"result":f"Pressed {key}"}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}

def _screenshot(path=""):
    try:
        import pyautogui
        out=path or f"screenshot_{int(time.time())}.png"
        img=pyautogui.screenshot(); img.save(out)
        return {"result":f"Screenshot saved: {out}","file":out,"size":os.path.getsize(out)}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}

def _open_app(path_or_name):
    try:
        if sys.platform=="win32":
            os.startfile(path_or_name)
        elif sys.platform=="darwin":
            subprocess.Popen(["open",path_or_name])
        else:
            subprocess.Popen(["xdg-open",path_or_name])
        return {"result":f"Opened: {path_or_name}"}
    except Exception as e: return {"error":str(e)}

def _list_windows():
    try:
        import pygetwindow as gw
        wins=[{"title":w.title,"active":w.isActive} for w in gw.getAllWindows()]
        return {"result":wins,"count":len(wins)}
    except ImportError: return {"error":"pip install pygetwindow"}
    except Exception as e: return {"error":str(e)}

def _run_command(cmd):
    try:
        r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=30)
        return {"result":r.stdout[-2000:] if r.stdout else r.stderr[-2000:],"returncode":r.returncode}
    except subprocess.TimeoutExpired: return {"error":"Command timed out (30s)"}
    except Exception as e: return {"error":str(e)}

def _file_manager(action="",path=""):
    actions={"list":lambda p:os.listdir(p) if os.path.isdir(p) else None,
             "info":lambda p:{"size":os.path.getsize(p),"modified":os.path.getmtime(p),"is_dir":os.path.isdir(p)} if os.path.exists(p) else None,
             "delete":lambda p:os.remove(p) if os.path.isfile(p) else None,
             "mkdir":lambda p:os.makedirs(p,exist_ok=True)}
    fn=actions.get(action)
    if not fn: return {"error":f"file_manager action: list|info|delete|mkdir"}
    try:
        r=fn(path)
        if r is None and action!="mkdir": return {"error":f"Path not found: {path}"}
        return {"result":r or f"{action} done","path":path}
    except Exception as e: return {"error":str(e)}

def _get_screen_size():
    try:
        import pyautogui; w,h=pyautogui.size(); return {"result":{"width":w,"height":h}}
    except ImportError: return {"error":"pip install pyautogui"}
    except Exception as e: return {"error":str(e)}
