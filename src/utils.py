import os
import sys
import time
import re
import difflib
import configparser
import subprocess
from typing import List, Tuple
from pynput import keyboard

# Safe instruction fallback for CTranslate2
if "CT2_FORCE_CPU_ISA" not in os.environ:
    os.environ["CT2_FORCE_CPU_ISA"] = "GENERIC"

def normalize_hotkey_string(hk_str: str) -> str:
    hk = hk_str.strip().lower()
    hk = hk.replace('<super>', '<cmd>').replace('<win>', '<cmd>').replace('<meta>', '<cmd>')
    return hk

def clean_text_output(text: str) -> str:
    text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
    text = re.sub(r'[^\w\s.,?!-]', '', text, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', text).strip()

class SettingsManager:
    def __init__(self, filename: str = "settings.ini"):
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.filepath = os.path.join(self.base_dir, filename)
        self.config = configparser.ConfigParser()
        self.load_or_create()

    def load_or_create(self):
        if not os.path.exists(self.filepath):
            self.create_default_config()
        else:
            self.config.read(self.filepath, encoding="utf-8")
            self.ensure_defaults()

    def create_default_config(self):
        self.config["General"] = {
            "language": "de",
            "hotkey": "<super>+o",
            "hotkey_enabled": "true",
            "update_rate_ms": "250",
            "context_window_seconds": "5.0",
            "editor_visible": "false",
            "auto_punctuation": "true",
            "autocorrect": "true"
        }
        self.config["Model"] = {
            "model_size": "base",
            "device": "auto",
            "compute_type": "int8",
            "custom_model_path": ""
        }
        self.config["Injection"] = {
            "engine": "dotool"
        }
        self.save()

    def ensure_defaults(self):
        defaults = {
            "General": {
                "language": "de",
                "hotkey": "<super>+o",
                "hotkey_enabled": "true",
                "update_rate_ms": "250",
                "context_window_seconds": "5.0",
                "editor_visible": "false",
                "auto_punctuation": "true",
                "autocorrect": "true"
            },
            "Model": {
                "model_size": "base",
                "device": "auto",
                "compute_type": "int8",
                "custom_model_path": ""
            },
            "Injection": {"engine": "pynput"}
        }
        modified = False
        for section, keys in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                modified = True
            for key, val in keys.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, str(val))
                    modified = True
        if modified:
            self.save()

    def save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            self.config.write(f)

    def get(self, section: str, option: str, fallback: str = "") -> str:
        return self.config.get(section, option, fallback=fallback)

    def getboolean(self, section: str, option: str, fallback: bool = False) -> bool:
        return self.config.getboolean(section, option, fallback=fallback)

    def getint(self, section: str, option: str, fallback: int = 0) -> int:
        return self.config.getint(section, option, fallback=fallback)

    def getfloat(self, section: str, option: str, fallback: float = 0.0) -> float:
        return self.config.getfloat(section, option, fallback=fallback)

    def set(self, section: str, option: str, value: str):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))
        self.save()

class CrossPlatformInjector:
    def __init__(self, key_controller: keyboard.Controller, settings: SettingsManager):
        self.key_controller = key_controller
        self.settings = settings
        self.engine = self.settings.get("Injection", "engine", fallback="dotool").lower()

        self.env = os.environ.copy()
        try:
            uid = os.getuid()
        except AttributeError:
            uid = 1000

        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
        self.env["YDOTOOL_SOCKET"] = os.path.join(xdg_runtime, ".ydotool_socket")

    def reload_engine(self):
        self.engine = self.settings.get("Injection", "engine", fallback="dotool").lower()

    def _dotool_type(self, text: str):
        if not text: return
        try:
            proc = subprocess.Popen(["dotool"], stdin=subprocess.PIPE, text=True, encoding="utf-8")
            proc.communicate(input=f"type {text}\n")
        except Exception as e:
            print(f"[-] dotool type failed: {e}")

    def _dotool_backspace(self, count: int):
        if count <= 0: return
        try:
            commands = "".join(["key backspace\n" for _ in range(count)])
            proc = subprocess.Popen(["dotool"], stdin=subprocess.PIPE, text=True, encoding="utf-8")
            proc.communicate(input=commands)
        except Exception as e:
            print(f"[-] dotool backspace failed: {e}")

    def _ydotool_type(self, text: str):
        if not text: return
        try:
            subprocess.run(["ydotool", "type", "--key-delay", "0", "--", text],
                           env=self.env, encoding="utf-8", check=True, capture_output=True)
        except Exception as e:
            print(f"[-] ydotool type failed: {e}")

    def _ydotool_backspace(self, count: int):
        if count <= 0: return
        try:
            key_args = ["14:1", "14:0"] * count
            subprocess.run(["ydotool", "key"] + key_args,
                           env=self.env, encoding="utf-8", check=True, capture_output=True)
        except Exception as e:
            print(f"[-] ydotool backspace failed: {e}")

    def inject(self, chars_to_remove: int, words_to_type: List[str]):
        if self.engine == "dotool":
            if chars_to_remove > 0: self._dotool_backspace(chars_to_remove)
            if words_to_type: self._dotool_type(" ".join(words_to_type) + " ")
        elif self.engine == "ydotool":
            if chars_to_remove > 0: self._ydotool_backspace(chars_to_remove)
            if words_to_type: self._ydotool_type(" ".join(words_to_type) + " ")
        else:
            if chars_to_remove > 0:
                for _ in range(chars_to_remove):
                    self.key_controller.press(keyboard.Key.backspace)
                    self.key_controller.release(keyboard.Key.backspace)
                time.sleep(0.015)
            if words_to_type:
                for char in (" ".join(words_to_type) + " "):
                    self.key_controller.type(char)

class TranscriptionStabilizer:
    def __init__(self):
        self.committed_words: List[str] = []
        self.last_words: List[str] = []
        self.stability_counts: List[int] = []
        self.STABILITY_THRESHOLD = 2 

    def process(self, new_words: List[str], force_flush: bool, auto_correct: bool) -> Tuple[int, List[str]]:
        current_stability = []
        for i, word in enumerate(new_words):
            if i < len(self.last_words) and word == self.last_words[i]:
                current_stability.append(self.stability_counts[i] + 1)
            else:
                current_stability.append(1)

        self.last_words = new_words
        self.stability_counts = current_stability
        stable_idx = 0
        for i, (word, stab) in enumerate(zip(new_words, current_stability)):
            has_punct = bool(re.search(r'[.,?!]', word))
            is_last_word = (i == len(new_words) - 1)

            if force_flush:
                stable_idx = len(new_words)
                break

            if (stab >= self.STABILITY_THRESHOLD or has_punct) and not is_last_word:
                stable_idx = i + 1
            else:
                break 

        current_stable_words = new_words[:stable_idx]
        words_to_remove, chars_to_remove, words_to_type = self._get_diff(
            self.committed_words, current_stable_words, auto_correct
        )

        if words_to_remove > 0:
            self.committed_words = self.committed_words[:-words_to_remove]
        if words_to_type:
            self.committed_words.extend(words_to_type)

        return chars_to_remove, words_to_type

    def _get_diff(self, committed: List[str], new_stable: List[str], auto_correct: bool):
        if not committed: return 0, 0, new_stable

        matcher = difflib.SequenceMatcher(None, committed, new_stable)
        valid_blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]
        
        if not valid_blocks:
            return len(committed), sum(len(w) + 1 for w in committed), new_stable

        if not auto_correct:
            last_block = valid_blocks[-1]
            new_start_idx = last_block.b + last_block.size
            return 0, 0, new_stable[new_start_idx:]

        opcodes = matcher.get_opcodes()
        diverge_i, diverge_j = len(committed), len(new_stable)

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal': continue
            if tag == 'delete' and i1 == 0: continue 
            if tag == 'insert' and j1 == 0: continue 
            diverge_i, diverge_j = i1, j1
            break

        words_to_remove = len(committed) - diverge_i
        chars_to_remove = sum(len(w) + 1 for w in committed[diverge_i:])
        words_to_type = new_stable[diverge_j:]
        return words_to_remove, chars_to_remove, words_to_type

    def reset(self):
        self.committed_words.clear()
        self.last_words.clear()
        self.stability_counts.clear()