import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk, ImageGrab, ImageChops, ImageDraw
import collections
try:
    Image.MAX_IMAGE_PIXELS = None
except:
    pass

import math
import json
import random
import time 
import sys 
import os 
import atexit 
import socket 
import subprocess
import runpy
import threading
import hashlib
import re
import traceback
try:
    import requests
except Exception:
    requests = None
pypresence_import_error = None
try:
    from pypresence import Presence
except Exception:
    Presence = None
    pypresence_import_error = traceback.format_exc()
try:
    import pyautogui
except Exception:
    pyautogui = None
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except Exception:
    cv2 = None
    np = None
    CV2_AVAILABLE = False
import shutil
import tempfile
import stat

# --- IPC設定 (多重起動防止) ---
HOST = '127.0.0.1'
PORT = 31500 
EXIT_COMMAND = b'ANIMATED_EXIT' 
CLIENT_TIMEOUT = 3.0 

# --- PyInstaller対応関数 ---
GITHUB_DEFAULT_OWNER = "ramune478"
GITHUB_DEFAULT_REPO = "hijikimame-plus"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if os.environ.get('HIJIKI_EMBEDDED_RUNNING') != '1':
    for _a in list(sys.argv[1:]):
        if _a.startswith('--exec-embedded='):
            _fname = _a.split('=', 1)[1]
            try:
                _script_path = resource_path(_fname)
            except Exception:
                _script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _fname)
            if os.path.exists(_script_path):
                try:
                    # remove the flag so the embedded script won't see it
                    sys.argv = [ _script_path ]
                    os.environ['HIJIKI_EMBEDDED_RUNNING'] = '1'
                    runpy.run_path(_script_path, run_name='__main__')
                finally:
                    sys.exit(0)
            else:
                print(f"embedded script not found: {_script_path}")
                sys.exit(1)

# --- 設定パラメータ ---
TRACKING_SPEED = 0.01          
COLLISION_DISTANCE_BASE = 50 
COLLISION_EXPANSION_RATE = 0.3 
BOUNCE_STRENGTH = 1.5          
UPDATE_INTERVAL = 30 
MAX_ACCEL_FORCE = 5            
THROW_MULTIPLIER = 3           
THROW_COOLDOWN_FRAMES = 20     
MOUSE_ACCELERATION_THROW_THRESHOLD = 40.0
MOUSE_ACCELERATION_THROW_MULTIPLIER = 3.0

# --- nijiki (虹き豆) アニメ関連デフォルト ---
NIJIKI_DEFAULT_FPS = 10
NIJIKI_CACHE_SIZE_DEFAULT = 6
NIJIKI_MAX_FRAMES_DEFAULT = 60

# --- 画面端バウンド関連デフォルト ---
EDGE_BOUNCE_STRENGTH = 0.8
EDGE_BOUNCE_COUNT_DEFAULT = 3
SETTINGS_FILE = "hijiki_settings.json"

# --- たこ焼き状態の設定 ---
TAKOYAKI_IMAGE_PATH = "takoyaki.png" 

# --- 目の描画に関する設定 ---
EYE_RADIUS = 3      
EYE_OFFSET_X = 10   
EYE_OFFSET_Y = 2   
CENTER_OFFSET_X = 0
CENTER_OFFSET_Y = 0
EYE_MOVEMENT_LIMIT = 4 

TRANSPARENT_COLOR = '#000001' 
DEFAULT_EYE_COLOR = 'black'
INVERTED_EYE_COLOR = 'white'

# アプリバージョン（リリースタグと一致させてください）
VERSION = "Snapshot-v2.3.5"

DISCORD_CLIENT_ID = "1507453857456721951"
DISCORD_ACTIVITY_STATE = "※これは完全な身内ネタアプリケーションです。"
DISCORD_REPO_URL = "https://github.com/ramune478/hijikimame-plus"
CUSTOM_COSMETIC_WARNING = "コスメティックは exe と同じフォルダに保存されます。重要なファイルと同じ場所ですので、管理にはご注意ください。"


def _self_replace_target(target_path, timeout=30):
    """実行中のバイナリ（sys.executable）を target_path にコピーする。
    target_path がロックされている限りリトライし、成功後に target_path を起動する。"""
    src = sys.executable
    try:
        start = time.time()
        while True:
            try:
                shutil.copyfile(src, target_path)
                try:
                    os.chmod(target_path, os.stat(src).st_mode | stat.S_IEXEC)
                except:
                    pass
                break
            except PermissionError:
                if time.time() - start > timeout:
                    return False
                time.sleep(0.5)
            except Exception:
                return False
        try:
            subprocess.Popen([target_path])
        except Exception:
            pass
        return True
    except Exception:
        return False


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def start_update_check_thread():
    try:
        t = threading.Thread(target=_check_and_initiate_update, daemon=True)
        t.start()
    except:
        pass


def _check_and_initiate_update():
    """GitHub Releases を確認して、更新があればダウンロード→自己置換フローを開始する。

    環境変数 `GITHUB_OWNER` と `GITHUB_REPO` を必須とし、プライベートの場合は
    `GITHUB_UPDATE_TOKEN` または `GITHUB_TOKEN` を利用してください。
    """
    if VERSION.startswith('Snapshot'):
        return
    if not getattr(sys, 'frozen', False):
        return
    if requests is None:
        return
    owner = os.environ.get('GITHUB_OWNER')
    repo = os.environ.get('GITHUB_REPO')
    if not owner or not repo:
        return
    token = os.environ.get('GITHUB_UPDATE_TOKEN') or os.environ.get('GITHUB_TOKEN')
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers=headers, timeout=10)
        if resp.status_code != 200:
            return
        rel = resp.json()
        tag = rel.get('tag_name')
        if not tag or tag == VERSION:
            return
        # try to find accompanying sha256 asset (preferred) for verification
        sha_expected = None
        for a in rel.get('assets', []):
            aname = a.get('name', '').lower()
            if aname.endswith('.sha256') or aname.endswith('.sha256.txt') or aname.endswith('.sha256sum'):
                sha_url = a.get('url')
                if sha_url:
                    try:
                        dl_sha_headers = dict(headers)
                        dl_sha_headers['Accept'] = 'application/octet-stream'
                        rsha = requests.get(sha_url, headers=dl_sha_headers, timeout=20)
                        if rsha.status_code == 200:
                            txt = rsha.text.strip()
                            m = re.search(r'([A-Fa-f0-9]{64})', txt)
                            if m:
                                sha_expected = m.group(1).lower()
                    except:
                        pass
                break
        exe_name = os.path.basename(sys.executable)
        asset = None
        for a in rel.get('assets', []):
            name = a.get('name', '')
            if name == exe_name or name.endswith('.exe'):
                asset = a
                break
        if not asset:
            return
        download_url = asset.get('url')
        if not download_url:
            return
        exe_dir = os.path.dirname(sys.executable)
        new_exe_path = os.path.join(exe_dir, exe_name + ".update.exe")
        tmp_path = new_exe_path + ".download"
        dl_headers = dict(headers)
        dl_headers["Accept"] = "application/octet-stream"
        with requests.get(download_url, headers=dl_headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
        # If we have an expected SHA, verify the download
        try:
            if sha_expected:
                actual = _sha256_of_file(tmp_path)
                if actual.lower() != sha_expected.lower():
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
                    return
        except Exception:
            try:
                os.remove(tmp_path)
            except:
                pass
            return
        try:
            if os.path.exists(new_exe_path):
                os.remove(new_exe_path)
            os.replace(tmp_path, new_exe_path)
        except Exception:
            try:
                os.rename(tmp_path, new_exe_path)
            except Exception:
                return
        try:
            subprocess.Popen([new_exe_path, '--self-replace', sys.executable], close_fds=True)
            sys.exit(0)
        except Exception:
            return
    except Exception:
        return

class HijikimameApp:
    def __init__(self, master):
        self.master = master
        self.server_socket = None 

        # 掴む・投げる機能用の変数
        self.is_dragging_stop = False 
        self.throw_cooldown = 0 
        self.drag_vx = 0
        self.drag_vy = 0 

        # --- 多重起動チェック ---
        if self._is_another_instance_running():
            self.master.destroy()
            sys.exit(0)
        else:
            self._start_ipc_server()
            atexit.register(self._close_ipc_server)
        
        # --- UI初期設定 ---
        master.title("ひじき豆")
        try:
            master.iconbitmap(resource_path('hijikimame_desktop.ico'))
        except:
            pass
        master.overrideredirect(True)
        master.wm_attributes("-transparentcolor", TRANSPARENT_COLOR) 

        self.settings = {
            'selected_mode': 0,
            'nijiki_fps': NIJIKI_DEFAULT_FPS,
            'nijiki_cache_size': NIJIKI_CACHE_SIZE_DEFAULT,
            'nijiki_max_frames': NIJIKI_MAX_FRAMES_DEFAULT,
            'tracking_speed': TRACKING_SPEED,
            'throw_speed_multiplier': 2.5,  
            'max_throw_multiplier': 10,
            'edge_bounce_count': EDGE_BOUNCE_COUNT_DEFAULT,
            'edge_bounce_strength': EDGE_BOUNCE_STRENGTH,
            'mouse_repulsion_enabled': True,
            'screen_boundary_mode': 'bounce',
            'custom_cosmetics': [],
            'show_cosmetic_warning': True,
            'character_scale': 100.0,
            'eye_radius': 100.0,
            'image_tracking_force_fullscreen': False,
            'image_tracking_min_match_score': 0.6,
            'eye_movement_limit': EYE_MOVEMENT_LIMIT,
            'image_tracking_interval': 1.0,
        }

        try:
            cfg = self.load_settings_file()
            if isinstance(cfg, dict):
                self.settings.update(cfg)
        except:
            pass

        self.nijiki_cache = collections.OrderedDict()
        self.nijiki_frame_index = 0
        self.nijiki_last_frame_time = time.time()
        self._nijiki_loader = None
        self.nijiki_indices = []
        self.nijiki_frames = None

        self.remaining_bounces = self.settings['edge_bounce_count']
        master.wm_attributes("-topmost", True)

        self.current_mode = 0 
        self.is_inverted = False
        self.target_position = None
        self.target_image_path = None
        self.target_image_template = None
        self.target_image_last_search = 0.0
        self._target_image_search_in_progress = False
        self._target_image_search_requested = False
        self._target_image_lost = False
        self.settings.setdefault('eye_offset_x', EYE_OFFSET_X)
        self.settings.setdefault('eye_offset_y', EYE_OFFSET_Y)
        self.settings.setdefault('center_offset_x', CENTER_OFFSET_X)
        self.settings.setdefault('center_offset_y', CENTER_OFFSET_Y)
        self.settings.setdefault('character_scale', 100.0)
        self.settings.setdefault('eye_radius', 100.0)
        self.settings.setdefault('image_tracking_min_match_score', 0.6)
        self.settings.setdefault('eye_movement_limit', EYE_MOVEMENT_LIMIT)
        self.settings.setdefault('image_tracking_interval', 1.0)
        self.settings.setdefault('image_tracking_force_fullscreen', False)
        self._normalize_custom_cosmetics()

        if isinstance(self.settings.get('target_position'), list) and len(self.settings.get('target_position')) == 2:
            try:
                self.target_position = (int(self.settings['target_position'][0]), int(self.settings['target_position'][1]))
            except:
                self.target_position = None
        if self.settings.get('target_image_path'):
            self.target_image_path = self.settings.get('target_image_path')
            try:
                self.target_image_template = self.load_image(self.target_image_path)
            except:
                self.target_image_template = None
            if self.target_image_template is None:
                self.target_image_path = None
                self.settings['target_image_path'] = None
                if int(self.settings.get('tracking_target_mode', 0)) == 2:
                    self.settings['tracking_target_mode'] = 0

        self.original_image_path = resource_path("hijikimame_body.png") 
        self.original_image = self.load_image(self.original_image_path)
        self.takoyaki_image_path = resource_path(TAKOYAKI_IMAGE_PATH)
        self.takoyaki_image = self.load_image(self.takoyaki_image_path)
        self.extra_image_path = resource_path('3.png')
        self.extra_image = self.load_image(self.extra_image_path)
        
        if self.original_image is None:
            master.destroy()
            return
            
        # Apply character scale to the initially displayed image
        display_img = self._get_display_image(self.original_image)
        self.current_display_image = display_img
        self.image_width, self.image_height = display_img.size
        self.tk_image = ImageTk.PhotoImage(display_img)

        screen_width = master.winfo_vrootwidth()
        screen_height = master.winfo_vrootheight()
        self.x = screen_width // 2 - self.image_width // 2
        self.y = screen_height // 2 - self.image_height // 2
        self.vx = 0
        self.vy = 0
        
        self.is_exiting = False       
        self.exit_frames = self.load_gif_frames(resource_path("exit_animation.gif")) 
        self.current_frame_index = 0  
        
        self.start_time = time.time() 
        self.selective_mask = self._create_selective_mask(self.original_image) 
        
        self.last_mouse_x = master.winfo_pointerx()
        self.last_mouse_y = master.winfo_pointery()

        master.geometry(f'{self.image_width}x{self.image_height}+{int(self.x)}+{int(self.y)}')
        
        self.canvas = tk.Canvas(master, width=self.image_width, height=self.image_height, 
                                bg=TRANSPARENT_COLOR, highlightthickness=0)
        self.canvas.pack()
        
        self.character_id = self.canvas.create_image(self.image_width // 2, self.image_height // 2, 
                                                     image=self.tk_image)

        base_center_x = self.image_width // 2 + self.settings.get('center_offset_x', CENTER_OFFSET_X)
        base_center_y = self.image_height // 2 + self.settings.get('center_offset_y', CENTER_OFFSET_Y)
        eye_offset_x, eye_offset_y = self._get_eye_offset()
        eye_r = int(self.settings.get('eye_radius', EYE_RADIUS))

        self.eye_left_id = self.canvas.create_oval(
            base_center_x - eye_offset_x - eye_r,
            base_center_y + eye_offset_y - eye_r,
            base_center_x - eye_offset_x + eye_r,
            base_center_y + eye_offset_y + eye_r,
            fill=DEFAULT_EYE_COLOR, tag='eye'
        )
        self.eye_right_id = self.canvas.create_oval(
            base_center_x + eye_offset_x - eye_r,
            base_center_y + eye_offset_y - eye_r,
            base_center_x + eye_offset_x + eye_r,
            base_center_y + eye_offset_y + eye_r,
            fill=DEFAULT_EYE_COLOR, tag='eye'
        )
        try:
            self.canvas.tag_raise(self.eye_left_id)
            self.canvas.tag_raise(self.eye_right_id)
        except:
            pass

        self.set_mode(self.settings.get('selected_mode', 0), save=False)
        self.update_position()
        
        self.canvas.bind("<Button-1>", self.start_drag_stop)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag_stop)
        self.canvas.bind("<Button-3>", self.open_edit_window)
        
        self.master.bind("<Control-h>", lambda e: self.start_exit_animation())
        self.master.bind("<Control-r>", lambda e: self.toggle_mode()) 
        self.master.bind("<Control-e>", lambda e: self.open_edit_window())
        self.master.bind("<Control-E>", lambda e: self.open_edit_window())
        
        self.master.after(100, self._check_ipc_command)
        self._latest_update_tag = None
        self._latest_update_body = None
        self._latest_update_download_url = None
        self._latest_update_sha_expected = None
        self._latest_update_script_url = None
        self._update_available = False
        self._update_button = None
        self.discord_presence = None
        self._discord_presence_retry_delay_ms = 30000
        self._discord_presence_retry_scheduled = False
        self.master.after(500, self.start_update_check_thread)
        self.master.after(1000, self._cleanup_update_file)
        try:
            self.start_discord_presence()
        except:
            pass
        try:
            self.master.after(200, lambda: self.open_edit_window())
        except:
            pass

    def _show_update_dialog(self, title, text):
        try:
            messagebox.showinfo(title, text)
        except:
            pass

    def _get_local_script_path(self):
        try:
            if getattr(sys, 'frozen', False):
                candidate = os.path.join(os.path.dirname(sys.executable), 'hijikimame_desktop.py')
                if os.path.isfile(candidate):
                    return candidate
                return None
            script_path = os.path.abspath(sys.argv[0])
            if os.path.isfile(script_path) and script_path.lower().endswith('.py'):
                return script_path
            if hasattr(sys, 'file'):
                script_path = os.path.abspath(__file__)
                if os.path.isfile(script_path):
                    return script_path
        except:
            pass
        return None

    def get_app_folder(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        try:
            return os.path.dirname(os.path.abspath(__file__))
        except:
            return os.path.abspath('.')

    def get_custom_cosmetic_path(self, filename):
        return os.path.join(self.get_app_folder(), filename)

    def _normalize_custom_cosmetics(self):
        custom_list = []
        for item in self.settings.get('custom_cosmetics', []):
            if isinstance(item, str):
                path = self.get_custom_cosmetic_path(item)
                if os.path.isfile(path):
                    custom_list.append(item)
        self.settings['custom_cosmetics'] = custom_list

    def _copy_cosmetic_file(self, source_path):
        try:
            app_dir = self.get_app_folder()
            base_name = os.path.basename(source_path)
            name, ext = os.path.splitext(base_name)
            safe_name = base_name
            counter = 1
            while os.path.exists(os.path.join(app_dir, safe_name)):
                safe_name = f"{name}-{counter}{ext}"
                counter += 1
            dest_path = os.path.join(app_dir, safe_name)
            shutil.copyfile(source_path, dest_path)
            return safe_name
        except:
            return None

    def add_custom_cosmetic(self, warning_var=None):
        try:
            if warning_var is None or warning_var.get():
                messagebox.showinfo("コスメティック追加の注意", CUSTOM_COSMETIC_WARNING)
        except:
            pass
        try:
            filename = filedialog.askopenfilename(
                title="コスメティック画像を選択",
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*")]
            )
            if not filename:
                return
            image = self.load_image(filename)
            if image is None:
                messagebox.showerror("読み込み失敗", "選択したファイルを画像として読み込めませんでした。")
                return
            copied_name = self._copy_cosmetic_file(filename)
            if not copied_name:
                messagebox.showerror("保存失敗", "コスメティックを保存できませんでした。")
                return
            if copied_name not in self.settings.get('custom_cosmetics', []):
                self.settings.setdefault('custom_cosmetics', []).append(copied_name)
            self.save_settings_file()
            self._normalize_custom_cosmetics()
            try:
                self._refresh_custom_cosmetic_listbox()
            except:
                pass
        except:
            pass

    def _refresh_custom_cosmetic_listbox(self):
        try:
            if not hasattr(self, '_custom_cosmetic_listbox'):
                return
            self._custom_cosmetic_listbox.delete(0, 'end')
            for item in self.settings.get('custom_cosmetics', []):
                self._custom_cosmetic_listbox.insert('end', item)
        except:
            pass

    def apply_custom_cosmetic_selection(self):
        try:
            if not hasattr(self, '_custom_cosmetic_listbox'):
                return
            sel = self._custom_cosmetic_listbox.curselection()
            if not sel:
                return
            index = int(sel[0])
            self.set_mode(5 + index)
        except:
            pass

    def remove_custom_cosmetic(self):
        try:
            if not hasattr(self, '_custom_cosmetic_listbox'):
                return
            sel = self._custom_cosmetic_listbox.curselection()
            if not sel:
                return
            index = int(sel[0])
            target_name = self.settings.get('custom_cosmetics', [])[index]
            if target_name in self.settings.get('custom_cosmetics', []):
                self.settings['custom_cosmetics'].pop(index)
            self.save_settings_file()
            self._normalize_custom_cosmetics()
            if self.current_mode >= 5 and self.current_mode - 5 >= len(self.settings.get('custom_cosmetics', [])):
                self.set_mode(0)
            self._refresh_custom_cosmetic_listbox()
        except:
            pass

    def _download_latest_script(self):
        if requests is None or not self._latest_update_script_url:
            return None
        try:
            resp = requests.get(self._latest_update_script_url, timeout=30)
            if resp.status_code == 200:
                return resp.content
        except:
            pass
        return None

    def _refresh_update_button(self):
        try:
            if self._update_button is None:
                return
            if self._update_available:
                if not self._update_button.winfo_ismapped():
                    self._update_button.pack(side='right', padx=2)
            else:
                self._update_button.pack_forget()
        except:
            pass

    def _perform_update(self):
        if not self._update_available:
            try:
                self._show_update_dialog("更新なし", "利用可能なアップデートはありません。")
            except:
                pass
            return
        try:
            release_notes = self._latest_update_body or '更新内容はありません。'
            message = f"{self._latest_update_tag} に揃えます。\n\n変更内容:\n{release_notes}"
            self._show_update_dialog("最新バージョンに揃える", message)
        except:
            pass
        threading.Thread(target=self._download_and_apply_update, daemon=True).start()

    def _download_and_apply_update(self):
        try:
            if requests is None:
                self.master.after(0, lambda: self._show_update_dialog("更新不可", "requests がインストールされていないため更新できません。"))
                return
            token = os.environ.get('GITHUB_UPDATE_TOKEN') or os.environ.get('GITHUB_TOKEN')
            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            script_updated = False
            script_path = self._get_local_script_path()
            script_data = self._download_latest_script()
            if script_data and script_path:
                try:
                    with open(script_path, 'wb') as f:
                        f.write(script_data)
                    script_updated = True
                except:
                    script_updated = False

            exe_downloaded = False
            exe_saved_path = None
            download_url = self._latest_update_download_url
            if download_url:
                dl_headers = dict(headers)
                dl_headers["Accept"] = "application/octet-stream"
                if getattr(sys, 'frozen', False):
                    exe_name = os.path.basename(sys.executable)
                    exe_dir = os.path.dirname(sys.executable)
                    new_exe_path = os.path.join(exe_dir, exe_name + ".update.exe")
                    tmp_path = new_exe_path + ".download"
                else:
                    script_dir = os.path.dirname(script_path) if script_path else os.getcwd()
                    asset_name = getattr(self, '_latest_update_asset_name', None) or os.path.basename(download_url)
                    if not asset_name.lower().endswith('.exe'):
                        asset_name = 'hijikimame-plus-latest.exe'
                    exe_saved_path = os.path.join(script_dir, asset_name)
                    tmp_path = exe_saved_path + ".download"
                try:
                    with requests.get(download_url, headers=dl_headers, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(tmp_path, 'wb') as f:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    f.write(chunk)
                    if self._latest_update_sha_expected:
                        actual = _sha256_of_file(tmp_path)
                        if actual.lower() != self._latest_update_sha_expected.lower():
                            try:
                                os.remove(tmp_path)
                            except:
                                pass
                            self.master.after(0, lambda: self._show_update_dialog("更新失敗", "ダウンロードファイルの検証に失敗しました。"))
                            return
                    if getattr(sys, 'frozen', False):
                        if os.path.exists(new_exe_path):
                            os.remove(new_exe_path)
                        os.replace(tmp_path, new_exe_path)
                        exe_downloaded = True
                    else:
                        if exe_saved_path and os.path.exists(exe_saved_path):
                            os.remove(exe_saved_path)
                        os.replace(tmp_path, exe_saved_path)
                        exe_downloaded = True
                except Exception:
                    try:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except:
                        pass
                    self.master.after(0, lambda: self._show_update_dialog("更新失敗", "更新のダウンロードまたは保存に失敗しました。"))
                    return

            if getattr(sys, 'frozen', False):
                if exe_downloaded:
                    try:
                        subprocess.Popen([new_exe_path, '--self-replace', sys.executable], close_fds=True)
                        self.master.after(0, lambda: self._show_update_dialog("更新中", "更新を適用しています。アプリを再起動します。"))
                        sys.exit(0)
                        return
                    except Exception:
                        pass
                if script_updated:
                    self.master.after(0, lambda: self._show_update_dialog("更新完了", "最新の Python スクリプトを保存しました。次回起動時に最新バージョンになります。"))
                    return
                self.master.after(0, lambda: self._show_update_dialog("更新完了", "最新バージョンの取得が完了しました。"))
                return

            # 非Frozen 実行時: Python スクリプトを更新し、exe がダウンロードできたら保存
            if script_updated and exe_downloaded:
                self.master.after(0, lambda: self._show_update_dialog("更新完了", f"最新バージョンに揃えました。exe を {exe_saved_path} に保存しました。"))
            elif script_updated:
                self.master.after(0, lambda: self._show_update_dialog("更新完了", "最新バージョンの Python スクリプトを保存しました。"))
            elif exe_downloaded:
                self.master.after(0, lambda: self._show_update_dialog("更新完了", f"最新バージョンの exe を {exe_saved_path} に保存しました。"))
            else:
                self.master.after(0, lambda: self._show_update_dialog("更新不可", "最新バージョンの取得に失敗しました。"))
        except Exception:
            pass

    def _cleanup_update_file(self):
        """アップデート完了後、.update.exe ファイルを削除する"""
        if getattr(sys, 'frozen', False):
            try:
                exe_name = os.path.basename(sys.executable)
                exe_dir = os.path.dirname(sys.executable)
                update_exe_path = os.path.join(exe_dir, exe_name + ".update.exe")
                if os.path.exists(update_exe_path):
                    try:
                        os.remove(update_exe_path)
                    except PermissionError:
                        pass
                    except Exception:
                        pass
            except Exception:
                pass

    def start_update_check_thread(self):
        try:
            t = threading.Thread(target=self._check_and_initiate_update, daemon=True)
            t.start()
        except:
            pass

    def _check_and_initiate_update(self):
        if VERSION.startswith('Snapshot'):
            return
        if requests is None:
            return
        owner = os.environ.get('GITHUB_OWNER', GITHUB_DEFAULT_OWNER)
        repo = os.environ.get('GITHUB_REPO', GITHUB_DEFAULT_REPO)
        if not owner or not repo:
            return
        token = os.environ.get('GITHUB_UPDATE_TOKEN') or os.environ.get('GITHUB_TOKEN')
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        try:
            resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers=headers, timeout=10)
            if resp.status_code != 200:
                return
            rel = resp.json()
            tag = rel.get('tag_name')
            body = rel.get('body', '') or '更新内容はありません。'
            if not tag or tag == VERSION:
                return
            self._latest_update_tag = tag
            self._latest_update_body = body
            self._latest_update_script_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{tag}/hijikimame_desktop.py"
            sha_expected = None
            for a in rel.get('assets', []):
                aname = a.get('name', '').lower()
                if aname.endswith('.sha256') or aname.endswith('.sha256.txt') or aname.endswith('.sha256sum'):
                    sha_url = a.get('url')
                    if sha_url:
                        try:
                            dl_sha_headers = dict(headers)
                            dl_sha_headers['Accept'] = 'application/octet-stream'
                            rsha = requests.get(sha_url, headers=dl_sha_headers, timeout=20)
                            if rsha.status_code == 200:
                                txt = rsha.text.strip()
                                m = re.search(r'([A-Fa-f0-9]{64})', txt)
                                if m:
                                    sha_expected = m.group(1).lower()
                        except:
                            pass
                    break
            exe_name = os.path.basename(sys.executable)
            asset = None
            for a in rel.get('assets', []):
                name = a.get('name', '')
                if name == exe_name or name.endswith('.exe'):
                    asset = a
                    break
            if asset:
                download_url = asset.get('url')
                if download_url:
                    self._latest_update_download_url = download_url
                    self._latest_update_asset_name = asset.get('name')
                else:
                    self._latest_update_download_url = None
                    self._latest_update_asset_name = None
            else:
                self._latest_update_download_url = None
                self._latest_update_asset_name = None
            self._latest_update_sha_expected = sha_expected
            self._update_available = True
            self.master.after(0, self._refresh_update_button)
            return
        except Exception:
            return

    def start_discord_presence(self):
        if Presence is None:
            error_text = 'pypresence module unavailable'
            if pypresence_import_error:
                error_text += '\n' + pypresence_import_error
            self._log_discord_debug('start_discord_presence', error_text)
            return
        try:
            self._disconnect_discord_presence()
            self.discord_presence = Presence(DISCORD_CLIENT_ID)
            self.discord_presence.connect()
            self._update_discord_presence()
            self._discord_presence_retry_scheduled = False
        except Exception:
            self.discord_presence = None
            if not self._discord_presence_retry_scheduled:
                self._discord_presence_retry_scheduled = True
                try:
                    self.master.after(self._discord_presence_retry_delay_ms, self.start_discord_presence)
                except Exception:
                    pass
            self._log_discord_debug('start_discord_presence', traceback.format_exc())

    def _update_discord_presence(self):
        if not getattr(self, 'discord_presence', None):
            return
        try:
            self.discord_presence.update(
                state=DISCORD_ACTIVITY_STATE,
                buttons=[
                    {"label": "GitHub", "url": DISCORD_REPO_URL}
                ]
            )
        except Exception:
            self._log_discord_debug('_update_discord_presence', traceback.format_exc())

    def _log_discord_debug(self, where, trace):
        try:
            path = os.path.join(tempfile.gettempdir(), 'hijikimame_discord.log')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {where}\n')
                f.write(trace)
                f.write('\n')
        except Exception:
            pass

    def _disconnect_discord_presence(self):
        if not getattr(self, 'discord_presence', None):
            return
        try:
            self.discord_presence.close()
        except Exception:
            pass
        self.discord_presence = None

    def _apply_mode(self, mode):
        if self.is_exiting:
            return
        self.current_mode = mode
        should_update_image = True
        new_image = self.original_image
        new_eye_color = DEFAULT_EYE_COLOR
        self.is_inverted = False

        if self.current_mode == 0:
            pass
        elif self.current_mode == 1:
            self.is_inverted = True
            new_eye_color = INVERTED_EYE_COLOR
            img_copy = self.original_image.copy()
            r, g, b, a = img_copy.split()
            r_inverted = r.point(lambda x: 255 - x)
            g_inverted = g.point(lambda x: 255 - x)
            b_inverted = b.point(lambda x: 255 - x)
            new_image = Image.merge("RGBA", (r_inverted, g_inverted, b_inverted, a))
        elif self.current_mode == 2:
            new_eye_color = DEFAULT_EYE_COLOR
            if self.takoyaki_image:
                new_image = self.takoyaki_image
        elif self.current_mode == 3:
            new_eye_color = DEFAULT_EYE_COLOR
            if not self.nijiki_cache and not getattr(self, '_nijiki_loader', None):
                try:
                    seq_dir = resource_path('nijiki')
                    use_sequence = False
                    try:
                        if os.path.isdir(seq_dir):
                            for fn in os.listdir(seq_dir):
                                if fn.lower().endswith('.png') and fn.lower().startswith('nijiki_'):
                                    use_sequence = True
                                    break
                    except:
                        use_sequence = False
                    if use_sequence:
                        try:
                            self._start_nijiki_sequence_loader(seq_dir)
                        except:
                            pass
                except:
                    pass
            if self.nijiki_cache:
                try:
                    if 0 in self.nijiki_cache:
                        first_photo = self.nijiki_cache.get(0)
                    else:
                        first_photo = next(iter(self.nijiki_cache.values()))
                    self.nijiki_frame_index = 0
                    self.nijiki_last_frame_time = time.time()
                    self.tk_image = first_photo
                    self.canvas.itemconfig(self.character_id, image=self.tk_image)
                    should_update_image = False
                except StopIteration:
                    pass
                try:
                    self.canvas.itemconfigure(self.eye_left_id, state='normal')
                    self.canvas.itemconfigure(self.eye_right_id, state='normal')
                    self.canvas.tag_raise(self.eye_left_id)
                    self.canvas.tag_raise(self.eye_right_id)
                except:
                    pass

        if should_update_image:
            display_img = self._get_display_image(new_image)
            self.current_display_image = display_img
            try:
                self._apply_image_size(display_img)
            except:
                pass
            self.tk_image = ImageTk.PhotoImage(display_img)
            self.canvas.itemconfig(self.character_id, image=self.tk_image)
        try:
            self.canvas.itemconfig(self.eye_left_id, fill=new_eye_color)
            self.canvas.itemconfig(self.eye_right_id, fill=new_eye_color)
            if self.current_mode != 3:
                self.canvas.itemconfigure(self.eye_left_id, state='normal')
                self.canvas.itemconfigure(self.eye_right_id, state='normal')
        except:
            pass

    def close_all_instances(self):
        """IPC経由で全てのインスタンスに終了コマンドを送り、自身も終了アニメを開始する"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect((HOST, PORT))
                s.sendall(EXIT_COMMAND)
        except:
            pass
        self.start_exit_animation()

    # --- IPC処理メソッド群 ---
    def _is_another_instance_running(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CLIENT_TIMEOUT) 
                s.connect((HOST, PORT))
                s.sendall(EXIT_COMMAND)
            return True 
        except: 
            return False

    def _start_ipc_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(1)
            self.server_socket.setblocking(False) 
        except:
            self.master.destroy()
            sys.exit(1)
            
    def _close_ipc_server(self):
        if self.server_socket: self.server_socket.close()

    def _check_ipc_command(self):
        if self.is_exiting or not self.server_socket: return 
        try:
            conn, addr = self.server_socket.accept()
            with conn:
                data = conn.recv(4096)
                if data == EXIT_COMMAND:
                    self.start_exit_animation()
                elif data.startswith(b'SETTINGS:'):
                    try:
                        payload = data[len(b'SETTINGS:'):].decode('utf-8')
                        settings = json.loads(payload)
                        self.apply_remote_settings(settings)
                    except:
                        pass
        except: pass
        self.master.after(100, self._check_ipc_command)

    # --- 画像処理・モード切替 ---
    def _create_selective_mask(self, image):
        img_rgb = image.convert('RGB')
        mask = Image.new('L', image.size, 0)
        R_MIN, G_MIN, B_MAX = 200, 180, 100 
        for x in range(image.width):
            for y in range(image.height):
                R, G, B = img_rgb.getpixel((x, y))
                is_yellow_body = (R >= R_MIN and G >= G_MIN and B <= B_MAX) and (abs(R - G) < 50)
                is_green_stem = (G > R * 1.5) 
                is_red_mouth = (R > G * 1.5 and B < 50) 
                if is_yellow_body and not is_green_stem and not is_red_mouth:
                    mask.putpixel((x, y), 255)
        return mask
        
    def load_image(self, path):
        try:
            im = Image.open(path).convert("RGBA")
        except:
            return None
        return im

    def _get_display_image(self, image):
        try:
            scale = float(self.settings.get('character_scale', 100.0)) / 100.0
        except:
            scale = 1.0
        if image is None or scale == 1.0:
            return image
        try:
            w = max(1, int(image.width * scale))
            h = max(1, int(image.height * scale))
            return image.resize((w, h), Image.LANCZOS)
        except:
            return image

    def _get_center_offset(self):
        return (int(self.settings.get('center_offset_x', CENTER_OFFSET_X)),
                int(self.settings.get('center_offset_y', CENTER_OFFSET_Y)))

    def _get_eye_offset(self):
        return (int(self.settings.get('eye_offset_x', EYE_OFFSET_X)),
                int(self.settings.get('eye_offset_y', EYE_OFFSET_Y)))

    def _update_eye_positions(self):
        base_center_x = self.image_width // 2 + self._get_center_offset()[0]
        base_center_y = self.image_height // 2 + self._get_center_offset()[1]
        eye_offset_x, eye_offset_y = self._get_eye_offset()
        lx = base_center_x - eye_offset_x
        ly = base_center_y + eye_offset_y
        rx = base_center_x + eye_offset_x
        ry = base_center_y + eye_offset_y
        eye_size_percent = float(self.settings.get('eye_radius', 100.0))
        r = max(0, int(EYE_RADIUS * eye_size_percent / 100.0))
        if r == 0:
            try:
                self.canvas.itemconfigure(self.eye_left_id, state='hidden')
                self.canvas.itemconfigure(self.eye_right_id, state='hidden')
            except:
                pass
            return
        try:
            self.canvas.itemconfigure(self.eye_left_id, state='normal')
            self.canvas.itemconfigure(self.eye_right_id, state='normal')
            self.canvas.coords(self.eye_left_id, lx-r, ly-r, lx+r, ly+r)
            self.canvas.coords(self.eye_right_id, rx-r, ry-r, rx+r, ry+r)
        except:
            pass

    def _apply_image_size(self, image):
        try:
            # Accept either a PIL Image (has .size) or a PhotoImage (has width/height methods)
            if hasattr(image, 'size'):
                self.image_width, self.image_height = image.size
            else:
                try:
                    self.image_width, self.image_height = image.width(), image.height()
                except:
                    return
            self.canvas.config(width=self.image_width, height=self.image_height)
            self.master.geometry(f'{self.image_width}x{self.image_height}+{int(self.x)}+{int(self.y)}')
            try:
                self.canvas.coords(self.character_id, self.image_width // 2, self.image_height // 2)
            except:
                pass
            self._update_eye_positions()
        except:
            pass

    def set_mode(self, mode, save=True):
        if self.is_exiting:
            return
        try:
            mode = int(mode)
        except:
            return
        if mode < 0:
            return
        self.current_mode = mode
        self.settings['selected_mode'] = mode
        if save:
            self.save_settings_file()
        try:
            self._refresh_character_buttons()
        except:
            pass

        should_update_image = True
        new_image = self.original_image
        new_eye_color = DEFAULT_EYE_COLOR
        self.is_inverted = False

        custom_cosmetics = self.settings.get('custom_cosmetics', [])
        if self.current_mode >= 5:
            custom_index = self.current_mode - 5
            if custom_index < 0 or custom_index >= len(custom_cosmetics):
                self.current_mode = 0
                self.settings['selected_mode'] = 0
                if not save:
                    self.save_settings_file()
            else:
                custom_path = self.get_custom_cosmetic_path(custom_cosmetics[custom_index])
                custom_image = self.load_image(custom_path)
                if custom_image is not None:
                    new_image = custom_image
                else:
                    self.current_mode = 0
                    self.settings['selected_mode'] = 0
                    if not save:
                        self.save_settings_file()

        if self.current_mode == 0:
            pass
        elif self.current_mode == 1:
            self.is_inverted = True
            new_eye_color = INVERTED_EYE_COLOR
            img_copy = self.original_image.copy()
            r, g, b, a = img_copy.split()
            r_inverted = r.point(lambda x: 255 - x)
            g_inverted = g.point(lambda x: 255 - x)
            b_inverted = b.point(lambda x: 255 - x)
            new_image = Image.merge("RGBA", (r_inverted, g_inverted, b_inverted, a))
        elif self.current_mode == 2:
            if self.takoyaki_image:
                new_image = self.takoyaki_image
        elif self.current_mode == 3:
            new_eye_color = DEFAULT_EYE_COLOR
            if not self.nijiki_cache and not getattr(self, '_nijiki_loader', None):
                try:
                    seq_dir = resource_path('nijiki')
                    use_sequence = False
                    try:
                        if os.path.isdir(seq_dir):
                            for fn in os.listdir(seq_dir):
                                if fn.lower().endswith('.png') and fn.lower().startswith('nijiki_'):
                                    use_sequence = True
                                    break
                    except:
                        use_sequence = False
                    if use_sequence:
                        try:
                            self._start_nijiki_sequence_loader(seq_dir)
                        except:
                            pass
                except:
                    pass
            if self.nijiki_cache:
                try:
                    if 0 in self.nijiki_cache:
                        first_photo = self.nijiki_cache.get(0)
                    else:
                        first_photo = next(iter(self.nijiki_cache.values()))
                    self.nijiki_frame_index = 0
                    self.nijiki_last_frame_time = time.time()
                    self.tk_image = first_photo
                    self._apply_image_size(first_photo)
                    self.canvas.itemconfig(self.character_id, image=self.tk_image)
                    should_update_image = False
                except StopIteration:
                    pass
                try:
                    self.canvas.itemconfigure(self.eye_left_id, state='normal')
                    self.canvas.itemconfigure(self.eye_right_id, state='normal')
                    self.canvas.tag_raise(self.eye_left_id)
                    self.canvas.tag_raise(self.eye_right_id)
                except:
                    pass
        elif self.current_mode == 4:
            if self.extra_image:
                new_image = self.extra_image

        if should_update_image:
            display_img = self._get_display_image(new_image)
            self.current_display_image = display_img
            try:
                self._apply_image_size(display_img)
            except:
                pass
            self.tk_image = ImageTk.PhotoImage(display_img)
            self.canvas.itemconfig(self.character_id, image=self.tk_image)
        try:
            self.canvas.itemconfig(self.eye_left_id, fill=new_eye_color)
            self.canvas.itemconfig(self.eye_right_id, fill=new_eye_color)
            if self.current_mode != 3:
                self.canvas.itemconfigure(self.eye_left_id, state='normal')
                self.canvas.itemconfigure(self.eye_right_id, state='normal')
        except:
            pass

    def toggle_mode(self):
        if self.is_exiting:
            return
        total_modes = 5 + len(self.settings.get('custom_cosmetics', []))
        if total_modes <= 0:
            total_modes = 5
        self.set_mode((self.current_mode + 1) % total_modes)

    def load_gif_frames(self, path):
        frames = []
        try:
            img = Image.open(path)
            nframes = getattr(img, 'n_frames', 1)
            max_frames = 60
            if nframes <= max_frames:
                indices = list(range(nframes))
            else:
                step = max(1, nframes // max_frames)
                indices = list(range(0, nframes, step))[:max_frames]
            for i in indices:
                img.seek(i)
                part = img.copy().convert('RGBA')
                # 各フレームを個別に扱い、前フレームとの累積合成を行わない。
                # 終了アニメーションでの不要なブレンドを防止するための変更。
                frame = part.copy()
                try:
                    if hasattr(self, 'image_width') and hasattr(self, 'image_height'):
                        target_w, target_h = self.image_width, self.image_height
                        fw, fh = frame.size
                        if fw > target_w or fh > target_h:
                            frame.thumbnail((target_w, target_h), Image.LANCZOS)
                except:
                    pass
                try:
                    data = list(frame.getdata())
                    newdata = []
                    for (r, g, b, a) in data:
                        if r < 16 and g < 16 and b < 16:
                            newdata.append((0, 0, 0, 0))
                        else:
                            newdata.append((r, g, b, a))
                    frame.putdata(newdata)
                except:
                    pass
                frames.append(ImageTk.PhotoImage(frame))
            return frames
        except Exception:
            return []

    def _start_nijiki_sequence_loader(self, dir_path):
        try:
            files = [f for f in os.listdir(dir_path) if f.lower().endswith('.png') and f.lower().startswith('nijiki_')]
            files.sort()
        except:
            return
        if not files:
            return
        self.nijiki_cache.clear()
        for i, fname in enumerate(files):
            try:
                p = os.path.join(dir_path, fname)
                im = Image.open(p).convert('RGBA')
                try:
                    if hasattr(self, 'image_width') and hasattr(self, 'image_height'):
                        target_w, target_h = self.image_width, self.image_height
                        fw, fh = im.size
                        if fw > target_w or fh > target_h:
                            im.thumbnail((target_w, target_h), Image.LANCZOS)
                except:
                    pass
                # scale frame according to character scale before creating PhotoImage
                im_disp = self._get_display_image(im)
                photo = ImageTk.PhotoImage(im_disp)
                self.nijiki_cache[i] = photo
            except:
                pass
        self.nijiki_indices = list(range(len(self.nijiki_cache)))
        if self.nijiki_cache:
            try:
                first = self.nijiki_cache.get(0, next(iter(self.nijiki_cache.values())))
                self.nijiki_frame_index = 0
                self.nijiki_last_frame_time = time.time()
                self.tk_image = first
                self.canvas.itemconfig(self.character_id, image=self.tk_image)
            except:
                pass

    def _get_tracking_target_mode_display(self):
        mode = int(self.settings.get('tracking_target_mode', 0))
        if mode == 1:
            return '追尾先: 指定位置'
        if mode == 2:
            return '追尾先: 画像'
        return '追尾先: マウス'

    def _get_target_status_text(self):
        mode = int(self.settings.get('tracking_target_mode', 0))
        if mode == 1:
            if self.target_position:
                return f'選択位置: {self.target_position[0]}, {self.target_position[1]}'
            return '選択位置: なし'
        if mode == 2:
            label = f'画像: {os.path.basename(self.target_image_path)}' if self.target_image_path else '画像: なし'
            if self.target_position:
                label += f' (現在: {self.target_position[0]}, {self.target_position[1]})'
            return label
        return 'マウス位置を追尾します'

    def _update_target_status_labels(self):
        try:
            if hasattr(self, '_target_mode_label'):
                self._target_mode_label.config(text=self._get_tracking_target_mode_display())
            if hasattr(self, '_target_status_label'):
                self._target_status_label.config(text=self._get_target_status_text())
        except:
            pass

    def _refresh_character_buttons(self):
        try:
            for mi, btn in getattr(self, '_character_buttons', {}).items():
                if mi == self.current_mode:
                    btn.config(relief='sunken', bg='#d0f0c0')
                else:
                    btn.config(relief='raised', bg='SystemButtonFace')
        except:
            pass

    def request_target_position_selection(self):
        try:
            if hasattr(self, '_target_overlay') and self._target_overlay.winfo_exists():
                return
        except:
            pass
        try:
            screen_w = self.master.winfo_vrootwidth()
            screen_h = self.master.winfo_vrootheight()
            self._target_overlay = tk.Toplevel(self.master)
            self._target_overlay.overrideredirect(True)
            self._target_overlay.attributes('-alpha', 0.2)
            self._target_overlay.attributes('-topmost', True)
            self._target_overlay.geometry(f'{screen_w}x{screen_h}+0+0')
            self._target_overlay.configure(bg='black')
            label = tk.Label(self._target_overlay, text='追跡する場所をクリックしてください\nESCでキャンセル', bg='black', fg='white', font=('Arial', 18))
            label.place(relx=0.5, rely=0.5, anchor='center')
            self._target_overlay.bind('<Button-1>', self._on_target_position_selected)
            label.bind('<Button-1>', self._on_target_position_selected)
            self._target_overlay.bind('<Escape>', lambda e: self._cancel_target_position_selection())
            self._target_overlay.focus_force()
        except:
            pass

    def _on_target_position_selected(self, event):
        try:
            x = event.x_root
            y = event.y_root
            self.target_position = (x, y)
            self.settings['target_position'] = [x, y]
            self.settings['tracking_target_mode'] = 1
            self._update_target_status_labels()
            self.save_settings_file()
            self.broadcast_settings()
        except:
            pass
        self._cancel_target_position_selection()

    def _cancel_target_position_selection(self):
        try:
            if hasattr(self, '_target_overlay') and self._target_overlay.winfo_exists():
                self._target_overlay.destroy()
        except:
            pass

    def choose_target_image(self):
        try:
            filename = filedialog.askopenfilename(parent=self.master, title='追跡する画像を選択', filetypes=[('画像ファイル', '*.png;*.jpg;*.jpeg;*.bmp;*.gif'), ('すべて', '*.*')])
            if not filename:
                return
            template = self.load_image(filename)
            if template is None:
                raise Exception('invalid image')
            self.target_image_template = template
            self.target_image_path = filename
            self.settings['target_image_path'] = filename
            self.settings['tracking_target_mode'] = 2
            self.settings['target_position'] = None
            self.target_position = None
            self.target_image_last_search = 0.0
            self._search_target_image_on_screen(force=True)
            self._update_target_status_labels()
            self.save_settings_file()
            self.broadcast_settings()
        except Exception:
            try:
                messagebox.showerror('画像選択エラー', '指定したファイルを読み込めませんでした。')
            except:
                pass

    def _grab_screen(self):
        try:
            if ImageGrab is None:
                return None
            # Temporarily hide canvas items (character + eyes) so they don't occlude the desktop
            hidden_items = []
            try:
                if hasattr(self, 'canvas'):
                    for item in self.canvas.find_all():
                        try:
                            prev = self.canvas.itemcget(item, 'state')
                        except:
                            prev = None
                        try:
                            self.canvas.itemconfigure(item, state='hidden')
                            hidden_items.append((item, prev))
                        except:
                            pass
                    try:
                        self.master.update()
                        time.sleep(0.02)
                    except:
                        pass
            except:
                hidden_items = []

            try:
                screen = ImageGrab.grab()
            finally:
                # restore previously-hidden items
                try:
                    for item, prev in hidden_items:
                        try:
                            if prev and prev != '':
                                self.canvas.itemconfigure(item, state=prev)
                            else:
                                self.canvas.itemconfigure(item, state='normal')
                        except:
                            pass
                    try:
                        self.master.update()
                    except:
                        pass
                except:
                    pass

            try:
                x = self.master.winfo_rootx()
                y = self.master.winfo_rooty()
                w = self.master.winfo_width()
                h = self.master.winfo_height()
                if w > 0 and h > 0:
                    if getattr(self, 'current_display_image', None) is not None and self.current_display_image.mode == 'RGBA':
                        mask = self.current_display_image.split()[3]
                        if mask.size == (w, h):
                            screen.paste((255, 0, 255), (x, y), mask)
                        else:
                            draw = ImageDraw.Draw(screen)
                            draw.rectangle([x, y, x + w, y + h], fill=(255, 0, 255))
                    else:
                        draw = ImageDraw.Draw(screen)
                        draw.rectangle([x, y, x + w, y + h], fill=(255, 0, 255))
            except:
                pass
            return screen
        except:
            return None

    def _find_template_on_screen_cv(self, screen, template, region=None):
        """OpenCVベースの高速テンプレートマッチ。画面とテンプレートは PIL Image。
        戻り値: (center_x, center_y, score) または None
        """
        if not CV2_AVAILABLE:
            return None
        try:
            # Crop to region if provided (region: (x,y,w,h))
            region_offset_x = 0
            region_offset_y = 0
            proc_screen = screen
            if region is not None:
                rx, ry, rw, rh = region
                proc_screen = screen.crop((rx, ry, rx + rw, ry + rh))
                region_offset_x = rx
                region_offset_y = ry

            # Convert to color BGR numpy arrays for OpenCV (no grayscale choice)
            screen_np = np.array(proc_screen.convert('RGB'))
            template_np = np.array(template.convert('RGB'))
            # Convert RGB->BGR for OpenCV
            screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
            template_bgr = cv2.cvtColor(template_np, cv2.COLOR_RGB2BGR)

            sh, sw = screen_bgr.shape[:2]
            th, tw = template_bgr.shape[:2]
            if tw > sw or th > sh:
                return None

            best_score = -1.0
            best_loc = None
            best_size = (tw, th)

            # Try a limited set of scales around 1.0 for speed and robustness
            scales = [1.0, 0.9, 1.1, 0.8, 1.25]
            screen_bgr_f = screen_bgr.astype(np.float32)
            for scale in scales:
                rw_t = max(6, int(tw * scale))
                rh_t = max(6, int(th * scale))
                if rw_t > sw or rh_t > sh:
                    continue
                try:
                    tmpl_resized = cv2.resize(template_bgr, (rw_t, rh_t), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
                    tmpl_resized_f = tmpl_resized.astype(np.float32)
                except Exception:
                    continue
                try:
                    res = cv2.matchTemplate(screen_bgr_f, tmpl_resized_f, cv2.TM_CCOEFF_NORMED)
                except Exception:
                    continue
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = float(max_val)
                    best_loc = max_loc
                    best_size = (rw_t, rh_t)

            if best_loc is None:
                return None

            min_score = float(self.settings.get('image_tracking_min_match_score', 0.6))
            if best_score < min_score:
                return None

            bx, by = best_loc
            bw, bh = best_size
            center_x = int(region_offset_x + bx + bw / 2)
            center_y = int(region_offset_y + by + bh / 2)
            return (center_x, center_y, best_score)
        except Exception:
            return None

    def _search_target_image_on_screen(self, force=False):
        if self.target_image_template is None:
            return
        now = time.time()
        tracking_interval = float(self.settings.get('image_tracking_interval', 1.0))
        if not force and now - self.target_image_last_search < tracking_interval:
            return
        if self._target_image_search_in_progress:
            self._target_image_search_requested = True
            return
        self._target_image_search_requested = False
        self._target_image_search_in_progress = True
        self.target_image_last_search = now
        template = self.target_image_template.copy()
        def worker():
            result = None
            try:
                # Enforce OpenCV-only tracking for speed and accuracy.
                if not CV2_AVAILABLE:
                    result = None
                    def _notify_no_cv():
                        try:
                            messagebox.showwarning('画像追跡エラー', 'OpenCV が必要です。OpenCV をインストールしてください。')
                        except:
                            pass
                        try:
                            self.settings['tracking_target_mode'] = 0
                            self.save_settings_file()
                            self.broadcast_settings()
                            self._update_target_status_labels()
                        except:
                            pass
                    try:
                        self.master.after(0, _notify_no_cv)
                    except:
                        pass
                else:
                    screen = self._grab_screen()
                    if screen is not None:
                        # Save debug captures for analysis
                        try:
                            dbg_ts = int(time.time() * 1000)
                            dbg_dir = os.path.join(tempfile.gettempdir(), 'hijikimame_debug')
                            try:
                                os.makedirs(dbg_dir, exist_ok=True)
                            except:
                                pass
                            full_path = os.path.join(dbg_dir, f'dbg_{dbg_ts}_full.png')
                            try:
                                screen.save(full_path)
                                print('DEBUG: saved full screen ->', full_path)
                            except Exception:
                                pass
                            tmpl_path = os.path.join(dbg_dir, f'dbg_{dbg_ts}_template.png')
                            try:
                                template.save(tmpl_path)
                                print('DEBUG: saved template ->', tmpl_path)
                            except Exception:
                                pass
                            if region is not None:
                                try:
                                    rx, ry, rw, rh = region
                                    region_img = screen.crop((rx, ry, rx + rw, ry + rh))
                                    region_path = os.path.join(dbg_dir, f'dbg_{dbg_ts}_region.png')
                                    region_img.save(region_path)
                                    print('DEBUG: saved region ->', region_path)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # If configured, force full-screen search; otherwise prioritize nearby region
                        force_fullscreen = bool(self.settings.get('image_tracking_force_fullscreen', False))
                        region = None
                        if not force_fullscreen and self.target_position:
                            px, py = self.target_position
                            region_size = 600
                            region = (
                                max(0, int(px - region_size // 2)),
                                max(0, int(py - region_size // 2)),
                                region_size,
                                region_size
                            )
                        # First try region-based CV search for speed
                        res_cv = self._find_template_on_screen_cv(screen, template, region=region)
                        result = res_cv
                        # If not found in region, try full-screen CV search
                        if result is None and region is not None:
                            result = self._find_template_on_screen_cv(screen, template, region=None)
            except:
                result = None
            try:
                self.master.after(0, lambda: self._finish_target_image_search(result))
            except:
                self._target_image_search_in_progress = False
        threading.Thread(target=worker, daemon=True).start()

    def _finish_target_image_search(self, result):
        self._target_image_search_in_progress = False
        if self.settings.get('tracking_target_mode') != 2 or self.target_image_path != self.settings.get('target_image_path'):
            if self._target_image_search_requested:
                self._target_image_search_requested = False
            return
        had_previous_position = self.target_position is not None
        if result:
            x, y, score = result
            self.target_position = (x, y)
            self.settings['target_position'] = [x, y]
            self._target_image_lost = False
        else:
            if had_previous_position:
                # Keep the last known location and stay in place until the target is found again.
                self._target_image_lost = True
            else:
                self.target_position = None
                self.settings['target_position'] = None
                self._target_image_lost = False
        self._update_target_status_labels()
        if self._target_image_search_requested:
            self._target_image_search_requested = False
            self._search_target_image_on_screen(force=True)

    def _find_template_on_screen(self, screen, template):
        try:
            # Always operate in RGB (color) for fallback; no grayscale option
            screen_proc_full = screen.convert('RGB')
            screen_proc = screen_proc_full
            template_proc = template.convert('RGB')
            sw, sh = screen_proc.size
            tw, th = template_proc.size
            if tw > sw or th > sh:
                return None
            scale = 1.0
            if sw > 800 or sh > 800:
                scale = max(sw / 800.0, sh / 800.0)
                screen_proc = screen_proc.resize((max(1, int(sw / scale)), max(1, int(sh / scale))), Image.LANCZOS)
                template_proc = template_proc.resize((max(1, int(tw / scale)), max(1, int(th / scale))), Image.LANCZOS)
            tw2, th2 = template_proc.size
            if tw2 < 8 or th2 < 8:
                return None
            step = max(1, min(4, max(1, tw2 // 16), max(1, th2 // 16)))
            small_template = template_proc.resize((64, 64), Image.LANCZOS)
            best_score = None
            best_xy = None
            for y in range(0, screen_proc.height - th2 + 1, step):
                for x in range(0, screen_proc.width - tw2 + 1, step):
                    patch = screen_proc.crop((x, y, x + tw2, y + th2)).resize((64, 64), Image.LANCZOS)
                    diff = ImageChops.difference(patch, small_template)
                    # color diff: sum of channel sums
                    score = sum(sum(px) for px in diff.getdata())
                    if best_score is None or score < best_score:
                        best_score = score
                        best_xy = (x, y)
            if best_xy is None:
                return None

            bx, by = best_xy
            refine_radius = max(8, step * 2)
            refined_score = best_score
            for y in range(max(0, by - refine_radius), min(screen_proc.height - th2, by + refine_radius) + 1):
                for x in range(max(0, bx - refine_radius), min(screen_proc.width - tw2, bx + refine_radius) + 1):
                    patch = screen_proc.crop((x, y, x + tw2, y + th2)).resize((64, 64), Image.LANCZOS)
                    diff = ImageChops.difference(patch, small_template)
                    score = sum(sum(px) for px in diff.getdata())
                    if score < refined_score:
                        refined_score = score
                        bx, by = x, y

            if scale > 1.0:
                orig_bx = min(sw - tw, int(bx * scale))
                orig_by = min(sh - th, int(by * scale))
                final_score = refined_score
                final_bx = orig_bx
                final_by = orig_by
                full_radius = max(16, int(scale * step * 2), 32)
                step2 = max(1, min(2, full_radius // 4))
                for y in range(max(0, orig_by - full_radius), min(sh - th, orig_by + full_radius) + 1, step2):
                    for x in range(max(0, orig_bx - full_radius), min(sw - tw, orig_bx + full_radius) + 1, step2):
                        patch = screen_proc_full.crop((x, y, x + tw, y + th)).resize((64, 64), Image.LANCZOS)
                        diff = ImageChops.difference(patch, small_template)
                        score = sum(sum(px) for px in diff.getdata())
                        if score < final_score:
                            final_score = score
                            final_bx = x
                            final_by = y
                bx, by = final_bx, final_by
                refined_score = final_score

            return int(bx + tw / 2), int(by + th / 2), refined_score
        except:
            return None

    def toggle_tracking_target_mode(self):
        try:
            mode = int(self.settings.get('tracking_target_mode', 0))
            for _ in range(3):
                mode = (mode + 1) % 3
                if mode == 1 and self.target_position is None:
                    continue
                if mode == 2 and self.target_image_template is None:
                    continue
                break
            if mode == 2 and self.target_image_template is None:
                mode = 0
            self.settings['tracking_target_mode'] = mode
            if mode == 2:
                self._search_target_image_on_screen(force=True)
            if mode == 0:
                self.settings['target_position'] = None
                self.target_position = None
            self._update_target_status_labels()
            self.save_settings_file()
            self.broadcast_settings()
        except:
            pass

    def clear_target_tracking(self):
        try:
            self.settings['tracking_target_mode'] = 0
            self.settings['target_position'] = None
            self.settings['target_image_path'] = None
            self.target_position = None
            self.target_image_path = None
            self.target_image_template = None
            self._target_image_search_in_progress = False
            self._update_target_status_labels()
            self.save_settings_file()
            self.broadcast_settings()
        except:
            pass

    # --- 編集ウィンドウ ---
    def open_edit_window(self, event=None):
        try:
            if hasattr(self, '_edit_win') and self._edit_win.winfo_exists():
                self._edit_win.lift()
                return
        except:
            pass

        self._edit_win = tk.Toplevel(self.master)
        self._edit_win.title("ひじき豆 - settings")
        try:
            self._edit_win.iconbitmap(resource_path('hijikimame_desktop.ico'))
        except:
            pass
        self._edit_win.attributes('-topmost', True)

        # 最上部: 操作ボタンフレーム (擬人化ボタンなど)
        try:
            top_btn_frame = tk.Frame(self._edit_win)
            top_btn_frame.pack(fill='x', pady=5)
            tk.Button(top_btn_frame, text="キャラ切替", command=self.toggle_mode).pack(side='left', padx=5)
            tk.Button(top_btn_frame, text="場所選択", command=self.request_target_position_selection).pack(side='left', padx=5)
            tk.Button(top_btn_frame, text="画像追跡設定", command=self.choose_target_image).pack(side='left', padx=5)
            tk.Button(top_btn_frame, text="追尾解除", command=self.clear_target_tracking).pack(side='left', padx=5)
            tk.Button(top_btn_frame, text="設定読込", command=self.import_settings_from_file).pack(side='right', padx=5)
            tk.Button(top_btn_frame, text="設定出力", command=self.export_settings_to_file).pack(side='right', padx=5)
        except:
            pass

        self._target_mode_label = tk.Label(self._edit_win, text=self._get_tracking_target_mode_display())
        self._target_mode_label.pack(anchor='w', padx=8, pady=2)
        self._target_status_label = tk.Label(self._edit_win, text=self._get_target_status_text())
        self._target_status_label.pack(anchor='w', padx=8, pady=2)

        content_container = tk.Frame(self._edit_win)
        content_container.pack(fill='both', expand=True)
        content_canvas = tk.Canvas(content_container, borderwidth=0, highlightthickness=0)
        content_scroll = tk.Scrollbar(content_container, orient='vertical', command=content_canvas.yview)
        self._edit_frame = tk.Frame(content_canvas)
        self._edit_frame.bind('<Configure>', lambda e: content_canvas.configure(scrollregion=content_canvas.bbox('all')))
        content_canvas.create_window((0, 0), window=self._edit_frame, anchor='nw')
        content_canvas.configure(yscrollcommand=content_scroll.set)
        content_canvas.pack(side='left', fill='both', expand=True)
        content_scroll.pack(side='right', fill='y')
        self._edit_win.geometry('400x520')
        self._edit_win.minsize(525, 750)

        # キャラクター選択
        char_frame = tk.LabelFrame(self._edit_frame, text='キャラクター選択')
        char_frame.pack(fill='both', padx=8, pady=5, expand=True)
        char_canvas = tk.Canvas(char_frame, borderwidth=0, highlightthickness=0, height=200)
        char_container = tk.Frame(char_canvas)
        char_container.bind('<Configure>', lambda e: char_canvas.configure(scrollregion=char_canvas.bbox('all')))
        char_canvas.create_window((0, 0), window=char_container, anchor='nw')
        char_canvas.pack(side='left', fill='both', expand=True)

        def _on_edit_mousewheel(event):
            try:
                if event.widget.winfo_toplevel() is not self._edit_win:
                    return
            except:
                pass
            if hasattr(event, 'delta') and event.delta:
                content_canvas.yview_scroll(int(-event.delta / 120), 'units')
            elif getattr(event, 'num', None) == 4:
                content_canvas.yview_scroll(-1, 'units')
            elif getattr(event, 'num', None) == 5:
                content_canvas.yview_scroll(1, 'units')
            return 'break'

        # Bind globally but only handle events originating from this edit window
        self._edit_win.bind_all('<MouseWheel>', _on_edit_mousewheel)
        self._edit_win.bind_all('<Button-4>', _on_edit_mousewheel)
        self._edit_win.bind_all('<Button-5>', _on_edit_mousewheel)

        def _cleanup_edit_mousewheel_bindings(event):
            try:
                self._edit_win.unbind_all('<MouseWheel>')
                self._edit_win.unbind_all('<Button-4>')
                self._edit_win.unbind_all('<Button-5>')
            except:
                pass

        self._edit_win.bind('<Destroy>', _cleanup_edit_mousewheel_bindings)

        self._character_buttons = {}
        mode_names = {
            0: '1. ひじき豆',
            1: '2. ろず',
            2: '3. たこ焼き',
            3: '4. 虹き豆',
            4: '5. オーバーローダーひじき豆'

        }
        for mi in range(5):
            btn = tk.Button(char_container, text=mode_names.get(mi, f'{mi+1}'), width=20,
                            command=lambda m=mi: self.set_mode(m))
            btn.pack(anchor='w', padx=4, pady=2)
            self._character_buttons[mi] = btn
        self._refresh_character_buttons()

        repulsion_var = tk.IntVar(value=1 if self.settings.get('mouse_repulsion_enabled', True) else 0)
        self.repulsion_var = repulsion_var
        repulsion_cb = tk.Checkbutton(self._edit_frame, text="ひじき豆の反発", variable=repulsion_var)
        repulsion_cb.pack(anchor='w', padx=8, pady=2)

        tk.Label(self._edit_frame, text="画面端の挙動:").pack(anchor='w', padx=8)
        boundary_mode_var = tk.StringVar(value=self.settings.get('screen_boundary_mode', 'bounce'))
        self.boundary_mode_var = boundary_mode_var
        boundary_menu = tk.OptionMenu(self._edit_frame, boundary_mode_var, 'bounce', 'stop', 'destroy')
        boundary_menu.config(width=20)
        boundary_menu.pack(fill='x', padx=8, pady=2)

        show_warning_var = tk.IntVar(value=1 if self.settings.get('show_cosmetic_warning', True) else 0)
        self.show_warning_var = show_warning_var
        show_warning_cb = tk.Checkbutton(self._edit_frame, text="コスメ追加時の警告を表示する", variable=show_warning_var)
        show_warning_cb.pack(anchor='w', padx=8, pady=2)

        custom_frame = tk.LabelFrame(self._edit_frame, text='カスタムコスメティック')
        custom_frame.pack(fill='both', padx=8, pady=5, expand=True)
        self._custom_cosmetic_listbox = tk.Listbox(custom_frame, height=5)
        self._custom_cosmetic_listbox.pack(fill='both', padx=4, pady=4, expand=True)
        custom_button_frame = tk.Frame(custom_frame)
        custom_button_frame.pack(fill='x', padx=4, pady=2)
        tk.Button(custom_button_frame, text='追加', command=lambda: self.add_custom_cosmetic(show_warning_var)).pack(side='left', padx=2)
        tk.Button(custom_button_frame, text='適用', command=self.apply_custom_cosmetic_selection).pack(side='left', padx=2)
        tk.Button(custom_button_frame, text='削除', command=self.remove_custom_cosmetic).pack(side='left', padx=2)
        self._refresh_custom_cosmetic_listbox()

        adjust_frame = tk.LabelFrame(self._edit_frame, text='コスメティック調整')
        adjust_frame.pack(fill='both', padx=8, pady=5, expand=True)
        tk.Label(adjust_frame, text='目のオフセット X:').pack(anchor='w', padx=4, pady=2)
        self.eye_x_scale = tk.Scale(adjust_frame, from_=-80, to=80, orient='horizontal')
        self.eye_x_scale.set(self.settings.get('eye_offset_x', EYE_OFFSET_X))
        self.eye_x_scale.pack(fill='x', padx=4)
        tk.Label(adjust_frame, text='目のオフセット Y:').pack(anchor='w', padx=4, pady=2)
        self.eye_y_scale = tk.Scale(adjust_frame, from_=-80, to=80, orient='horizontal')
        # Y軸はUI操作の向きを反転して扱う（スケール値 = -設定値）
        self.eye_y_scale.set(-self.settings.get('eye_offset_y', EYE_OFFSET_Y))
        self.eye_y_scale.pack(fill='x', padx=4)
        tk.Label(adjust_frame, text='キャラ中心オフセット X:').pack(anchor='w', padx=4, pady=2)
        self.center_x_scale = tk.Scale(adjust_frame, from_=-120, to=120, orient='horizontal')
        self.center_x_scale.set(self.settings.get('center_offset_x', CENTER_OFFSET_X))
        self.center_x_scale.pack(fill='x', padx=4)
        tk.Label(adjust_frame, text='キャラ中心オフセット Y:').pack(anchor='w', padx=4, pady=2)
        self.center_y_scale = tk.Scale(adjust_frame, from_=-120, to=120, orient='horizontal')
        # Y軸はUI操作の向きを反転して扱う（スケール値 = -設定値）
        self.center_y_scale.set(-self.settings.get('center_offset_y', CENTER_OFFSET_Y))
        self.center_y_scale.pack(fill='x', padx=4)

        # キャラの大きさ（0～200%）
        tk.Label(adjust_frame, text='キャラの大きさ (%):').pack(anchor='w', padx=4, pady=2)
        self.char_scale = tk.Scale(adjust_frame, from_=0, to=200, orient='horizontal')
        self.char_scale.set(self.settings.get('character_scale', 100.0))
        self.char_scale.pack(fill='x', padx=4)

        # 目の大きさ（0～200%）
        tk.Label(adjust_frame, text='目の大きさ (%):').pack(anchor='w', padx=4, pady=2)
        self.eye_size_scale = tk.Scale(adjust_frame, from_=0, to=200, orient='horizontal')
        self.eye_size_scale.set(self.settings.get('eye_radius', 100.0))
        self.eye_size_scale.pack(fill='x', padx=4)

        # 目の動く範囲
        tk.Label(adjust_frame, text='目の動く範囲:').pack(anchor='w', padx=4, pady=2)
        self.eye_movement_scale = tk.Scale(adjust_frame, from_=0, to=20, orient='horizontal')
        self.eye_movement_scale.set(self.settings.get('eye_movement_limit', EYE_MOVEMENT_LIMIT))
        self.eye_movement_scale.pack(fill='x', padx=4)

        tk.Label(self._edit_frame, text="追尾速度:").pack(anchor='w', padx=8)
        self.tracking_scale = tk.Scale(self._edit_frame, from_=0.0, to=0.1, resolution=0.001, orient='horizontal')
        self.tracking_scale.set(self.settings.get('tracking_speed', TRACKING_SPEED))
        self.tracking_scale.pack(fill='x', padx=8)

        tk.Label(self._edit_frame, text="投げ速度倍率:").pack(anchor='w', padx=8)
        self.throw_scale = tk.Scale(self._edit_frame, from_=0.1, to=10, resolution=0.1, orient='horizontal')
        self.throw_scale.set(self.settings.get('throw_speed_multiplier', 3.0))
        self.throw_scale.pack(fill='x', padx=8)

        tk.Label(self._edit_frame, text="投げ 最大倍率:").pack(anchor='w', padx=8)
        self.max_throw_scale = tk.Scale(self._edit_frame, from_=1, to=50, orient='horizontal')
        self.max_throw_scale.set(self.settings.get('max_throw_multiplier', 15))
        self.max_throw_scale.pack(fill='x', padx=8)

        tk.Label(self._edit_frame, text="画像追尾間隔 (秒):").pack(anchor='w', padx=8)
        self.image_tracking_scale = tk.Scale(self._edit_frame, from_=0.0, to=2.0, resolution=0.1, orient='horizontal')
        self.image_tracking_scale.set(self.settings.get('image_tracking_interval', 1.0))
        self.image_tracking_scale.pack(fill='x', padx=8)
        fullscreen_var = tk.IntVar(value=1 if self.settings.get('image_tracking_force_fullscreen', False) else 0)
        self.fullscreen_var = fullscreen_var
        fullscreen_cb = tk.Checkbutton(self._edit_frame, text="軽量化: 全画面追尾を常に行う", variable=fullscreen_var)
        fullscreen_cb.pack(anchor='w', padx=8, pady=2)
        tk.Label(self._edit_frame, text="軽量化: 追尾受理最低スコア:").pack(anchor='w', padx=8)
        self.image_tracking_score_scale = tk.Scale(self._edit_frame, from_=0.0, to=1.0, resolution=0.01, orient='horizontal')
        self.image_tracking_score_scale.set(self.settings.get('image_tracking_min_match_score', 0.6))
        self.image_tracking_score_scale.pack(fill='x', padx=8, pady=(0,8))

        tk.Label(self._edit_frame, text="画面端バウンド回数:").pack(anchor='w', padx=8)
        self.bounce_scale = tk.Scale(self._edit_frame, from_=0, to=20, orient='horizontal')
        self.bounce_scale.set(self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT))
        self.bounce_scale.pack(fill='x', padx=8)

        tk.Label(self._edit_frame, text="バウンド強さ:").pack(anchor='w', padx=8)
        self.bounce_strength_scale = tk.Scale(self._edit_frame, from_=0.0, to=1.5, resolution=0.05, orient='horizontal')
        self.bounce_strength_scale.set(self.settings.get('edge_bounce_strength', EDGE_BOUNCE_STRENGTH))
        self.bounce_strength_scale.pack(fill='x', padx=8)

        tk.Label(self._edit_frame, text="虹き豆 再生速度 (FPS):").pack(anchor='w', padx=8)
        self.nijiki_scale = tk.Scale(self._edit_frame, from_=1, to=60, orient='horizontal')
        self.nijiki_scale.set(self.settings.get('nijiki_fps', NIJIKI_DEFAULT_FPS))
        self.nijiki_scale.pack(fill='x', padx=8)

        def apply_settings():
            self.settings['nijiki_fps'] = int(self.nijiki_scale.get())
            self.settings['mouse_repulsion_enabled'] = bool(repulsion_var.get())
            self.settings['tracking_speed'] = float(self.tracking_scale.get())
            self.settings['throw_speed_multiplier'] = float(self.throw_scale.get())
            self.settings['max_throw_multiplier'] = float(self.max_throw_scale.get())
            self.settings['edge_bounce_count'] = int(self.bounce_scale.get())
            self.settings['edge_bounce_strength'] = float(self.bounce_strength_scale.get())
            self.settings['screen_boundary_mode'] = boundary_mode_var.get()
            self.settings['show_cosmetic_warning'] = bool(show_warning_var.get())
            self.settings['eye_offset_x'] = int(self.eye_x_scale.get())
            # Y軸はUI上で向きを反転して扱う
            self.settings['eye_offset_y'] = -int(self.eye_y_scale.get())
            self.settings['center_offset_x'] = int(self.center_x_scale.get())
            # Y軸はUI上で向きを反転して扱う
            self.settings['center_offset_y'] = -int(self.center_y_scale.get())
            # キャラと目のサイズ（%表記）
            try:
                self.settings['character_scale'] = float(self.char_scale.get())
            except:
                self.settings['character_scale'] = 100.0
            try:
                self.settings['eye_radius'] = float(self.eye_size_scale.get())
            except:
                self.settings['eye_radius'] = 100.0
            try:
                self.settings['eye_movement_limit'] = float(self.eye_movement_scale.get())
            except:
                self.settings['eye_movement_limit'] = EYE_MOVEMENT_LIMIT
            try:
                self.settings['image_tracking_interval'] = float(self.image_tracking_scale.get())
            except:
                self.settings['image_tracking_interval'] = 1.0
            self.settings['image_tracking_force_fullscreen'] = bool(fullscreen_var.get())
            try:
                self.settings['image_tracking_min_match_score'] = float(self.image_tracking_score_scale.get())
            except:
                self.settings['image_tracking_min_match_score'] = 0.6
            if not self.is_dragging_stop and self.throw_cooldown == 0:
                self.remaining_bounces = self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT)
            try:
                self.save_settings_file()
            except:
                pass
            try:
                # Re-apply current mode to update displayed image scale/size
                self.set_mode(self.current_mode, save=False)
            except:
                pass
            try:
                self._update_eye_positions()
            except:
                pass
            try:
                self.broadcast_settings()
            except:
                pass

        # 下部ボタンエリア
        bottom_frame = tk.Frame(self._edit_win)
        bottom_frame.pack(fill='x', padx=8, pady=10)

        # 初期化関数
        def reset_settings():
            self.settings['nijiki_fps'] = NIJIKI_DEFAULT_FPS
            self.settings['tracking_speed'] = TRACKING_SPEED
            self.settings['throw_speed_multiplier'] = 2.5
            self.settings['max_throw_multiplier'] = 10
            self.settings['edge_bounce_count'] = EDGE_BOUNCE_COUNT_DEFAULT
            self.settings['edge_bounce_strength'] = EDGE_BOUNCE_STRENGTH
            self.settings['mouse_repulsion_enabled'] = True
            self.settings['screen_boundary_mode'] = 'bounce'
            self.settings['show_cosmetic_warning'] = True
            self.settings['selected_mode'] = 0
            self.settings['tracking_target_mode'] = 0
            self.settings['target_position'] = None
            self.settings['target_image_path'] = None
            self.settings['custom_cosmetics'] = []
            self.settings['eye_offset_x'] = EYE_OFFSET_X
            self.settings['eye_offset_y'] = EYE_OFFSET_Y
            self.settings['center_offset_x'] = CENTER_OFFSET_X
            self.settings['center_offset_y'] = CENTER_OFFSET_Y
            self.settings['character_scale'] = 100.0
            self.settings['eye_radius'] = 100.0
            self.settings['eye_movement_limit'] = EYE_MOVEMENT_LIMIT
            self.settings['image_tracking_interval'] = 1.0
            self.settings['image_tracking_force_fullscreen'] = False
            self.settings['image_tracking_min_match_score'] = 0.6
            self.target_position = None
            self.target_image_path = None
            self.target_image_template = None
            self.target_image_last_search = 0.0
            self._target_image_search_in_progress = False
            self.current_mode = 0
            self.nijiki_scale.set(NIJIKI_DEFAULT_FPS)
            self.tracking_scale.set(TRACKING_SPEED)
            self.throw_scale.set(2.5)
            self.max_throw_scale.set(10)
            self.bounce_scale.set(EDGE_BOUNCE_COUNT_DEFAULT)
            self.bounce_strength_scale.set(EDGE_BOUNCE_STRENGTH)
            repulsion_var.set(1)
            show_warning_var.set(1)
            boundary_mode_var.set('bounce')
            fullscreen_var.set(0)
            # スライダー側の表示値は Y を反転しているので注意
            self.eye_x_scale.set(EYE_OFFSET_X)
            self.eye_y_scale.set(-EYE_OFFSET_Y)
            self.center_x_scale.set(CENTER_OFFSET_X)
            self.center_y_scale.set(-CENTER_OFFSET_Y)
            self.char_scale.set(100.0)
            self.eye_size_scale.set(100.0)
            self.eye_movement_scale.set(EYE_MOVEMENT_LIMIT)
            self.image_tracking_scale.set(1.0)
            self.image_tracking_score_scale.set(0.6)
            try:
                self._refresh_character_buttons()
            except:
                pass
            try:
                self._refresh_custom_cosmetic_listbox()
            except:
                pass
            self.set_mode(0)
            self._update_target_status_labels()
            apply_settings()

        # ボタンを下に配置
        tk.Button(bottom_frame, text="初期化", command=reset_settings).pack(side='left', padx=2)
        tk.Button(bottom_frame, text="適用", command=apply_settings).pack(side='left', padx=2)
        self._update_button = tk.Button(bottom_frame, text="最新バージョンに揃える", bg="#8fbc8f", command=self._perform_update)
        if self._update_available:
            self._update_button.pack(side='right', padx=2)
        tk.Button(bottom_frame, text="閉じる", command=self._edit_win.destroy).pack(side='right', padx=2)
        tk.Button(bottom_frame, text="全て閉じる", bg="#ffcccb", command=self.close_all_instances).pack(side='right', padx=2)

        self.master.after(1500, self._poll_settings_file)

    def broadcast_settings(self):
        try:
            data = b'SETTINGS:' + json.dumps(self.settings).encode('utf-8')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5); s.connect((HOST, PORT)); s.sendall(data)
        except:
            pass

    def apply_remote_settings(self, settings_dict):
        try:
            settings_dict = dict(settings_dict)
            if 'edit_enabled' in settings_dict:
                settings_dict.pop('edit_enabled', None)
            for k, v in settings_dict.items():
                self.settings[k] = v
            self.remaining_bounces = int(self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT))
        except:
            pass

    def _poll_settings_file(self):
        try:
            p = resource_path(SETTINGS_FILE)
            if os.path.exists(p):
                m = os.path.getmtime(p)
                if getattr(self, '_settings_mtime', None) is None or m != self._settings_mtime:
                    self._settings_mtime = m
                    cfg = self.load_settings_file()
                    if isinstance(cfg, dict):
                        self.apply_remote_settings(cfg)
        except:
            pass
        if not self.is_exiting:
            self.master.after(1500, self._poll_settings_file)

    def save_settings_file(self):
        try:
            settings_to_save = dict(self.settings)
            if 'edit_enabled' in settings_to_save:
                settings_to_save.pop('edit_enabled', None)
            with open(resource_path(SETTINGS_FILE), 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_settings_file(self):
        try:
            p = resource_path(SETTINGS_FILE)
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return None
        return None

    def export_settings_to_file(self):
        try:
            p = filedialog.asksaveasfilename(parent=self.master, defaultextension='.json', filetypes=[('JSON','*.json')], title='設定を保存')
            if not p:
                return
            settings_to_save = dict(self.settings)
            if 'edit_enabled' in settings_to_save:
                settings_to_save.pop('edit_enabled', None)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
            try:
                messagebox.showinfo('保存完了', f'設定を保存しました: {p}')
            except:
                pass
        except Exception:
            try:
                messagebox.showerror('保存失敗', '設定の保存に失敗しました。')
            except:
                pass

    def import_settings_from_file(self):
        try:
            p = filedialog.askopenfilename(parent=self.master, title='設定ファイルを選択', filetypes=[('JSON','*.json'), ('すべて', '*.*')])
            if not p:
                return
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise Exception('invalid')
            for k, v in data.items():
                self.settings[k] = v
            # Ensure our keys and types
            self.settings.setdefault('tracking_speed', TRACKING_SPEED)
            self.settings.setdefault('throw_speed_multiplier', 2.5)
            self.settings.setdefault('max_throw_multiplier', 10)
            self.settings.setdefault('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT)
            self.settings.setdefault('edge_bounce_strength', EDGE_BOUNCE_STRENGTH)
            self.settings.setdefault('mouse_repulsion_enabled', True)
            self.settings.setdefault('screen_boundary_mode', 'bounce')
            self.settings.setdefault('show_cosmetic_warning', True)
            self.settings.setdefault('nijiki_fps', NIJIKI_DEFAULT_FPS)
            self.settings.setdefault('selected_mode', 0)
            self.settings.setdefault('tracking_target_mode', 0)
            self.settings.setdefault('target_position', None)
            self.settings.setdefault('target_image_path', None)
            self.settings.setdefault('custom_cosmetics', [])
            self.settings.setdefault('image_tracking_force_fullscreen', False)
            self.settings.setdefault('image_tracking_min_match_score', 0.6)
            self.settings.setdefault('character_scale', 100.0)
            self.settings.setdefault('eye_radius', 100.0)
            self.settings.setdefault('eye_movement_limit', EYE_MOVEMENT_LIMIT)
            self.settings.setdefault('image_tracking_interval', 1.0)
            try:
                if isinstance(self.settings.get('target_position'), list) and len(self.settings.get('target_position')) == 2:
                    try:
                        self.target_position = (int(self.settings['target_position'][0]), int(self.settings['target_position'][1]))
                    except:
                        self.target_position = None
                else:
                    self.target_position = None
            except:
                self.target_position = None
            if self.settings.get('target_image_path'):
                self.target_image_path = self.settings.get('target_image_path')
                try:
                    self.target_image_template = self.load_image(self.target_image_path)
                except:
                    self.target_image_template = None
                if self.target_image_template is None:
                    self.target_image_path = None
                    self.settings['target_image_path'] = None
                    if int(self.settings.get('tracking_target_mode', 0)) == 2:
                        self.settings['tracking_target_mode'] = 0
            else:
                self.target_image_path = None
                self.target_image_template = None
            try:
                self.settings['eye_offset_x'] = int(self.settings.get('eye_offset_x', EYE_OFFSET_X))
            except:
                self.settings['eye_offset_x'] = EYE_OFFSET_X
            try:
                self.settings['eye_offset_y'] = int(self.settings.get('eye_offset_y', EYE_OFFSET_Y))
            except:
                self.settings['eye_offset_y'] = EYE_OFFSET_Y
            try:
                self.settings['center_offset_x'] = int(self.settings.get('center_offset_x', CENTER_OFFSET_X))
            except:
                self.settings['center_offset_x'] = CENTER_OFFSET_X
            try:
                self.settings['center_offset_y'] = int(self.settings.get('center_offset_y', CENTER_OFFSET_Y))
            except:
                self.settings['center_offset_y'] = CENTER_OFFSET_Y
            try:
                self.settings['character_scale'] = float(self.settings.get('character_scale', 100.0))
            except:
                self.settings['character_scale'] = 100.0
            try:
                self.settings['eye_radius'] = float(self.settings.get('eye_radius', 100.0))
            except:
                self.settings['eye_radius'] = 100.0
            try:
                self.settings['eye_movement_limit'] = float(self.settings.get('eye_movement_limit', EYE_MOVEMENT_LIMIT))
            except:
                self.settings['eye_movement_limit'] = EYE_MOVEMENT_LIMIT
            try:
                self.settings['image_tracking_interval'] = float(self.settings.get('image_tracking_interval', 1.0))
            except:
                self.settings['image_tracking_interval'] = 1.0
            # persist
            try:
                self.save_settings_file()
            except:
                pass
            # update UI if open
            try:
                if hasattr(self, '_edit_win') and self._edit_win.winfo_exists():
                    try:
                        self.eye_x_scale.set(self.settings.get('eye_offset_x', EYE_OFFSET_X))
                        self.eye_y_scale.set(-self.settings.get('eye_offset_y', EYE_OFFSET_Y))
                        self.center_x_scale.set(self.settings.get('center_offset_x', CENTER_OFFSET_X))
                        self.center_y_scale.set(-self.settings.get('center_offset_y', CENTER_OFFSET_Y))
                        self.char_scale.set(self.settings.get('character_scale', 100.0))
                        self.eye_size_scale.set(self.settings.get('eye_radius', 100.0))
                        self.eye_movement_scale.set(self.settings.get('eye_movement_limit', EYE_MOVEMENT_LIMIT))
                        self.image_tracking_scale.set(self.settings.get('image_tracking_interval', 1.0))
                        self.image_tracking_score_scale.set(self.settings.get('image_tracking_min_match_score', 0.6))
                        if hasattr(self, 'fullscreen_var'):
                            self.fullscreen_var.set(1 if self.settings.get('image_tracking_force_fullscreen', False) else 0)
                        if hasattr(self, 'repulsion_var'):
                            self.repulsion_var.set(1 if self.settings.get('mouse_repulsion_enabled', True) else 0)
                        if hasattr(self, 'boundary_mode_var'):
                            self.boundary_mode_var.set(self.settings.get('screen_boundary_mode', 'bounce'))
                        if hasattr(self, 'show_warning_var'):
                            self.show_warning_var.set(1 if self.settings.get('show_cosmetic_warning', True) else 0)
                        self.tracking_scale.set(self.settings.get('tracking_speed', TRACKING_SPEED))
                        self.throw_scale.set(self.settings.get('throw_speed_multiplier', 2.5))
                        self.max_throw_scale.set(self.settings.get('max_throw_multiplier', 10))
                        self.bounce_scale.set(self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT))
                        self.bounce_strength_scale.set(self.settings.get('edge_bounce_strength', EDGE_BOUNCE_STRENGTH))
                        self.nijiki_scale.set(self.settings.get('nijiki_fps', NIJIKI_DEFAULT_FPS))
                        self._refresh_custom_cosmetic_listbox()
                    except:
                        pass
            except:
                pass
            try:
                self.set_mode(self.current_mode, save=False)
                self._update_eye_positions()
                self.broadcast_settings()
            except:
                pass
            try:
                messagebox.showinfo('読み込み完了', '設定を読み込みました。')
            except:
                pass
        except Exception:
            try:
                messagebox.showerror('読み込み失敗', '設定ファイルの読み込みに失敗しました。')
            except:
                pass

    def start_drag_stop(self, event):
        if event.num == 1:
            self.is_dragging_stop = True; self.vx = 0; self.vy = 0; self.throw_cooldown = 0 
            self.last_mouse_x = self.master.winfo_pointerx()
            self.last_mouse_y = self.master.winfo_pointery()
            self.drag_vx = 0; self.drag_vy = 0
            self.canvas.bind("<B1-Motion>", self.do_move)

    def stop_drag_stop(self, event):
        if event.num == 1:
            self.is_dragging_stop = False
            mouse_speed = math.hypot(self.drag_vx, self.drag_vy)
            dynamic_multiplier = min(mouse_speed * self.settings.get('throw_speed_multiplier', 2.5), self.settings.get('max_throw_multiplier', 10))
            self.vx = self.drag_vx * dynamic_multiplier
            self.vy = self.drag_vy * dynamic_multiplier
            # 保存: 投擲直後の初速（エッジ衝突時の最小反射力算出に使う）
            try:
                self._last_throw_velocity = (self.vx, self.vy)
            except:
                self._last_throw_velocity = (0, 0)
            self.throw_cooldown = THROW_COOLDOWN_FRAMES
            self.remaining_bounces = self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT)
            self.drag_vx = 0; self.drag_vy = 0
            self.canvas.unbind("<B1-Motion>")

    def do_move(self, event):
        if self.is_dragging_stop:
            current_x = self.master.winfo_pointerx()
            current_y = self.master.winfo_pointery()
            self.drag_vx = current_x - self.last_mouse_x
            self.drag_vy = current_y - self.last_mouse_y
            self.last_mouse_x = current_x; self.last_mouse_y = current_y
            self.update_eyes_only()

    def update_eyes_only(self):
        eye_size_percent = float(self.settings.get('eye_radius', 100.0))
        if eye_size_percent == 0:
            try:
                self.canvas.itemconfigure(self.eye_left_id, state='hidden')
                self.canvas.itemconfigure(self.eye_right_id, state='hidden')
            except:
                pass
            return
        try:
            self.canvas.itemconfigure(self.eye_left_id, state='normal')
            self.canvas.itemconfigure(self.eye_right_id, state='normal')
        except:
            pass
        mouse_x = self.master.winfo_pointerx()
        mouse_y = self.master.winfo_pointery()
        char_center_x = self.x + self.image_width // 2 + self._get_center_offset()[0]
        char_center_y = self.y + self.image_height // 2 + self._get_center_offset()[1]
        dx = mouse_x - char_center_x; dy = mouse_y - char_center_y
        dist = math.hypot(dx, dy)
        if dist != 0:
            dx_u, dy_u = dx / dist, dy / dist
        else:
            dx_u, dy_u = 0, 0
        eye_movement_limit = float(self.settings.get('eye_movement_limit', EYE_MOVEMENT_LIMIT))
        move_dist = min(dist * 0.1, eye_movement_limit)
        move_x, move_y = dx_u * move_dist, dy_u * move_dist
        base_center_x = self.image_width // 2 + self._get_center_offset()[0]
        base_center_y = self.image_height // 2 + self._get_center_offset()[1]
        eye_offset_x, eye_offset_y = self._get_eye_offset()
        lx, ly = base_center_x - eye_offset_x + move_x, base_center_y + eye_offset_y + move_y
        rx, ry = base_center_x + eye_offset_x + move_x, base_center_y + eye_offset_y + move_y
        r = max(0, int(EYE_RADIUS * eye_size_percent / 100.0))
        self.canvas.coords(self.eye_left_id, lx-r, ly-r, lx+r, ly+r)
        self.canvas.coords(self.eye_right_id, rx-r, ry-r, rx+r, ry+r)

    def update_position(self):
        if self.is_exiting: return
        mouse_x = self.master.winfo_pointerx()
        mouse_y = self.master.winfo_pointery()
        mouse_vx = mouse_x - self.last_mouse_x
        mouse_vy = mouse_y - self.last_mouse_y
        mouse_speed = math.hypot(mouse_vx, mouse_vy)
        # compute mouse acceleration using previous frame velocity
        prev_vx = getattr(self, '_last_mouse_vx', 0)
        prev_vy = getattr(self, '_last_mouse_vy', 0)
        mouse_ax = mouse_vx - prev_vx
        mouse_ay = mouse_vy - prev_vy
        mouse_a_mag = math.hypot(mouse_ax, mouse_ay)

        target_mode = int(self.settings.get('tracking_target_mode', 0))
        if target_mode == 2:
            if self.target_image_template:
                self._search_target_image_on_screen()
            else:
                target_mode = 0
                self.settings['tracking_target_mode'] = 0
        if target_mode == 1 and self.target_position:
            target_x, target_y = self.target_position
        elif target_mode == 2 and self.target_position:
            target_x, target_y = self.target_position
        else:
            target_x, target_y = mouse_x, mouse_y

        char_center_x = self.x + self.image_width // 2 + self._get_center_offset()[0]
        char_center_y = self.y + self.image_height // 2 + self._get_center_offset()[1]
        if target_mode == 2 and self._target_image_lost and self.target_position is not None:
            target_x, target_y = char_center_x, char_center_y
            self.vx = 0; self.vy = 0
        dx_char = target_x - char_center_x; dy_char = target_y - char_center_y
        distance = math.hypot(dx_char, dy_char)
        touch_margin = max(16, min(self.image_width, self.image_height) // 6)
        is_mouse_over_char = (self.x - touch_margin <= mouse_x <= self.x + self.image_width + touch_margin and
                               self.y - touch_margin <= mouse_y <= self.y + self.image_height + touch_margin)

        # If the user is holding the character, follow cursor as before
        if self.is_dragging_stop:
            self.x = mouse_x - (self.image_width // 2)
            self.y = mouse_y - (self.image_height // 2)
            self.vx = 0; self.vy = 0
        else:
            repulsion_enabled = self.settings.get('mouse_repulsion_enabled', True)
            # Detect sudden cursor acceleration and convert to an impulse throw
            try:
                if repulsion_enabled and is_mouse_over_char and mouse_a_mag >= MOUSE_ACCELERATION_THROW_THRESHOLD:
                    self.vx = mouse_ax * MOUSE_ACCELERATION_THROW_MULTIPLIER
                    self.vy = mouse_ay * MOUSE_ACCELERATION_THROW_MULTIPLIER
                    self.throw_cooldown = THROW_COOLDOWN_FRAMES
                    self.remaining_bounces = self.settings.get('edge_bounce_count', EDGE_BOUNCE_COUNT_DEFAULT)
                    self._last_throw_velocity = (self.vx, self.vy)
            except Exception:
                pass

            # if in throw cooldown, continue coasting with decay
            if self.throw_cooldown > 0:
                self.throw_cooldown -= 1; self.vx *= 0.92; self.vy *= 0.92
                self.x += self.vx; self.y += self.vy
            else:
                repulsion_enabled = self.settings.get('mouse_repulsion_enabled', True)
                if repulsion_enabled and is_mouse_over_char:
                    actual_bounce_force = max(20, mouse_speed * BOUNCE_STRENGTH, 80.0 / max(distance, 1.0))
                    if distance != 0:
                        nx = dx_char / distance
                        ny = dy_char / distance
                        self.vx = -nx * actual_bounce_force
                        self.vy = -ny * actual_bounce_force
                        push_back = max(self.image_width, self.image_height) * 0.25
                        self.x -= nx * push_back
                        self.y -= ny * push_back
                    else:
                        angle = random.uniform(0, 2 * math.pi)
                        self.vx = math.cos(angle) * actual_bounce_force
                        self.vy = math.sin(angle) * actual_bounce_force
                else:
                    track_speed = float(self.settings.get('tracking_speed', TRACKING_SPEED))
                    self.vx = (self.vx + dx_char * track_speed) * 0.85
                    self.vy = (self.vy + dy_char * track_speed) * 0.85
                self.x += self.vx; self.y += self.vy

        # remember last mouse velocity and position for next-frame accel calculation
        self._last_mouse_vx = mouse_vx
        self._last_mouse_vy = mouse_vy
        self.last_mouse_x = mouse_x; self.last_mouse_y = mouse_y

        screen_w = max(self.master.winfo_vrootwidth(), self.master.winfo_screenwidth())
        screen_h = max(self.master.winfo_vrootheight(), self.master.winfo_screenheight())
        vroot_x = self.master.winfo_vrootx()
        vroot_y = self.master.winfo_vrooty()
        strg = self.settings.get('edge_bounce_strength', EDGE_BOUNCE_STRENGTH)
        # cap to avoid extremely large velocities after reflection
        max_cap = max(screen_w, screen_h) * 0.6
        boundary_mode = self.settings.get('screen_boundary_mode', 'bounce')
        # X axis edge handling
        if self.x < vroot_x or self.x > vroot_x + screen_w - self.image_width:
            if boundary_mode == 'destroy':
                self.start_exit_animation()
                return
            self.x = max(vroot_x, min(self.x, vroot_x + screen_w - self.image_width))
            if boundary_mode == 'bounce':
                if self.throw_cooldown > 0:
                    # reflect velocity and apply strength; do not consume remaining_bounces here
                    self.vx = -self.vx * float(strg)
                    # if velocity is very small (damped), use last throw velocity to ensure a noticeable bounce
                    try:
                        lvx = getattr(self, '_last_throw_velocity', (0, 0))[0]
                    except:
                        lvx = 0
                    if abs(self.vx) < 2 and abs(lvx) > 0:
                        self.vx = -math.copysign(max(10, abs(lvx) * float(strg)), lvx)
                    # clamp magnitude
                    if self.vx > max_cap: self.vx = max_cap
                    if self.vx < -max_cap: self.vx = -max_cap
                elif self.remaining_bounces > 0:
                    self.vx *= -float(strg)
                    self.remaining_bounces -= 1
                    if self.vx > max_cap: self.vx = max_cap
                    if self.vx < -max_cap: self.vx = -max_cap
                else:
                    self.vx = 0
            else:  # stop
                self.vx = 0

        # Y axis edge handling (same rules)
        if self.y < vroot_y or self.y > vroot_y + screen_h - self.image_height:
            if boundary_mode == 'destroy':
                self.start_exit_animation()
                return
            self.y = max(vroot_y, min(self.y, vroot_y + screen_h - self.image_height))
            if boundary_mode == 'bounce':
                if self.throw_cooldown > 0:
                    self.vy = -self.vy * float(strg)
                    try:
                        lvy = getattr(self, '_last_throw_velocity', (0, 0))[1]
                    except:
                        lvy = 0
                    if abs(self.vy) < 2 and abs(lvy) > 0:
                        self.vy = -math.copysign(max(10, abs(lvy) * float(strg)), lvy)
                    if self.vy > max_cap: self.vy = max_cap
                    if self.vy < -max_cap: self.vy = -max_cap
                elif self.remaining_bounces > 0:
                    self.vy *= -float(strg)
                    self.remaining_bounces -= 1
                    if self.vy > max_cap: self.vy = max_cap
                    if self.vy < -max_cap: self.vy = -max_cap
                else:
                    self.vy = 0
            else:  # stop
                self.vy = 0

        if self.current_mode == 3 and self.nijiki_indices:
            fps = max(1, int(self.settings.get('nijiki_fps', NIJIKI_DEFAULT_FPS)))
            if time.time() - self.nijiki_last_frame_time >= (1.0 / fps):
                self.nijiki_frame_index = (self.nijiki_frame_index + 1) % len(self.nijiki_indices)
                f = self.nijiki_cache.get(self.nijiki_indices[self.nijiki_frame_index])
                if f: self.canvas.itemconfig(self.character_id, image=f)
                self.nijiki_last_frame_time = time.time()

        self.master.geometry(f"+{int(self.x)}+{int(self.y)}"); self.update_eyes_only()
        if not self.is_exiting:
            self.master.after(UPDATE_INTERVAL, self.update_position)

    def start_exit_animation(self):
        if self.is_exiting: return 
        if not self.exit_frames:
            self.master.destroy(); return
        self.is_exiting = True
        self.canvas.itemconfigure(self.eye_left_id, state='hidden')
        self.canvas.itemconfigure(self.eye_right_id, state='hidden')
        # prepare a fully transparent final frame to avoid residual-pixel artifacts
        try:
            self._transparent_frame = ImageTk.PhotoImage(Image.new('RGBA', (self.image_width, self.image_height), (0,0,0,0)))
        except Exception:
            self._transparent_frame = None
        self.play_exit_frame()

    def play_exit_frame(self):
        if self.current_frame_index < len(self.exit_frames):
            self.canvas.itemconfig(self.character_id, image=self.exit_frames[self.current_frame_index])
            self.current_frame_index += 1; self.master.after(20, self.play_exit_frame)
        else:
            # Try an aggressive clear: set window alpha to fully transparent and delete the canvas item
            try:
                try:
                    self.master.wm_attributes('-alpha', 0.0)
                except:
                    pass
                try:
                    self.canvas.delete(self.character_id)
                except:
                    pass
                try:
                    self.master.update_idletasks()
                except:
                    pass
            except:
                pass
            # Short delay to ensure the GUI updates before destroying
            try:
                self.master.after(10, lambda: self.master.destroy())
            except:
                self.master.destroy()

if __name__ == "__main__":
    # 自己置換フロー（ダウンロードした新しい exe が起動されたときの処理）
    if '--self-replace' in sys.argv:
        try:
            idx = sys.argv.index('--self-replace')
            target_path = sys.argv[idx+1] if len(sys.argv) > idx+1 else None
            if target_path:
                _self_replace_target(target_path)
        except Exception:
            pass
        sys.exit(0)

    # 通常起動時は更新チェックを実行（フロー開始 -> 必要ならダウンロードして置換プロセスを起動し、現在プロセスは終了する）
    root = tk.Tk()
    app = HijikimameApp(root)
    root.mainloop()
