import os
import sys
import time
import gc
import re
import threading
import multiprocessing
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from pynput import keyboard
import tkinter as tk


# Ausgelagerte Module
from utils import SettingsManager, CrossPlatformInjector, TranscriptionStabilizer, normalize_hotkey_string, clean_text_output
from gui import DictationUI

# Globale Konstanten
SAMPLE_RATE = 16000      
SILENCE_THRESHOLD = 1.0  


class AppCore:
    def __init__(self):
        self.settings = SettingsManager()
        self.is_recording = False
        self.model_loaded = False
        self.model = None

        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        
        self.stabilizer = TranscriptionStabilizer()
        self.global_context_prompt = ""

        self.key_controller = keyboard.Controller()
        self.injector = CrossPlatformInjector(self.key_controller, self.settings)
        self.hotkey_listener = None

        # UI initialisieren
        self.ui = DictationUI(
            settings=self.settings,
            on_toggle_record=self.toggle_recording,
            on_hotkey_toggle=self.on_hotkey_toggle,
            on_lang_change=self.change_language
        )
        
        self.restart_hotkey_listener()

        # Audio Stream starten
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype='float32', callback=self.audio_callback
        )
        self.stream.start()

        threading.Thread(target=self.load_model, daemon=True).start()
        threading.Thread(target=self.live_inference_worker, daemon=True).start()
        
        self.ui.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_hotkey_toggle(self):
        current = self.settings.getboolean("General", "hotkey_enabled", fallback=True)
        new_val = not current
        self.settings.set("General", "hotkey_enabled", str(new_val).lower())
        self.ui.update_hotkey_btn()
        self.restart_hotkey_listener()

    def restart_hotkey_listener(self):
        if self.hotkey_listener is not None:
            try: self.hotkey_listener.stop()
            except: pass
            self.hotkey_listener = None

        if self.settings.getboolean("General", "hotkey_enabled", fallback=True):
            raw_hk = self.settings.get("General", "hotkey", fallback="<super>+h")
            norm_hk = normalize_hotkey_string(raw_hk)
            try:
                self.hotkey_listener = keyboard.GlobalHotKeys({norm_hk: self.toggle_recording})
                self.hotkey_listener.start()
            except Exception as e:
                print(f"[-] Failed to bind hotkey '{raw_hk}': {e}")

    def change_language(self, new_lang_code):
        self.settings.set("General", "language", new_lang_code)
        self.ui.update_status("Lade neues Modell...", "#D97706")
        self.model_loaded = False 
        threading.Thread(target=self.load_model, daemon=True).start()

    def load_model(self):
        try:
            model_size = self.settings.get("Model", "model_size", fallback="base")
            device = self.settings.get("Model", "device", fallback="auto")
            compute_type = self.settings.get("Model", "compute_type", fallback="int8")
            custom_path = self.settings.get("Model", "custom_model_path", fallback="").strip()
            kwargs = {"device": device, "compute_type": compute_type}
            if custom_path and os.path.isdir(custom_path):
                kwargs["download_root"] = custom_path

            self.model = WhisperModel(model_size, **kwargs)
            self.model_loaded = True
            self.ui.update_status("Bereit (Idle)", "#059669")
        except Exception as e:
            print(f"[-] Load failed: {e}")
            self.ui.update_status("Fehler (Check Config)", "#DC2626")

    def audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            with self.buffer_lock:
                self.audio_buffer.extend(indata.flatten())

    def toggle_recording(self):
        if not self.model_loaded: return
        self.is_recording = not self.is_recording

        if self.is_recording:
            with self.buffer_lock:
                self.audio_buffer.clear()
            self.stabilizer.reset()
            self.global_context_prompt = ""
            
            self.ui.set_recording_state(True)
            self.ui.update_status("Hört zu...", "#DC2626")
        else:
            self.ui.set_recording_state(False)
            self.ui.update_status("Bereit (Idle)", "#059669")

    def inject_text(self, chars_to_remove: int, words_to_type: list[str]):
        is_editor_focused = (self.ui.editor_visible and (self.ui.focus_get() == self.ui.editor_text))
        if is_editor_focused:
            self.ui.after(0, lambda c=chars_to_remove, w=words_to_type: self.stream_to_editor(c, w))
        else:
            self.injector.inject(chars_to_remove, words_to_type)
            
    def stream_to_editor(self, chars_to_remove: int, words_to_type: list[str]):
        if chars_to_remove > 0:
            self.ui.editor_text.delete(f"end - 1 c - {chars_to_remove} c", "end - 1 c")
        if words_to_type:
            self.ui.editor_text.insert(tk.END, " ".join(words_to_type) + " ")
            self.ui.editor_text.see(tk.END)

    def live_inference_worker(self):
        while True:
            update_ms = self.settings.getint("General", "update_rate_ms", fallback=250)
            time.sleep(max(0.1, update_ms / 1000.0))
            if not self.is_recording or not self.model: continue

            with self.buffer_lock:
                if len(self.audio_buffer) < (SAMPLE_RATE * 0.3): continue
                audio_snapshot = np.array(self.audio_buffer, dtype=np.float32)
                snapshot_samples = len(self.audio_buffer)

            audio_duration = snapshot_samples / SAMPLE_RATE
            lang_code = self.settings.get("General", "language", fallback="de")
            active_prompt = self.global_context_prompt if self.global_context_prompt else "raw spoken words"

            segments_gen, _ = self.model.transcribe(
                audio_snapshot, beam_size=1, language=lang_code,
                initial_prompt=active_prompt, vad_filter=True
            )
            segments = list(segments_gen)

            autocorrect = self.settings.getboolean("General", "autocorrect", fallback=True)
            auto_punct = self.settings.getboolean("General", "auto_punctuation", fallback=True)

            if not segments:
                if audio_duration > SILENCE_THRESHOLD:
                    if self.stabilizer.last_words:
                        chars_rem, words_add = self.stabilizer.process(self.stabilizer.last_words, True, autocorrect)
                        if chars_rem > 0 or words_add:
                            self.inject_text(chars_rem, words_add)
                    self.flush_buffers(snapshot_samples)
                continue

            last_speech_end = segments[-1].end
            time_since_speech = audio_duration - last_speech_end
            max_ctx_dur = self.settings.getfloat("General", "context_window_seconds", fallback=5.0)

            force_flush = (time_since_speech > SILENCE_THRESHOLD or audio_duration > max_ctx_dur)
            raw_text = " ".join([seg.text for seg in segments])
            clean_text = clean_text_output(raw_text)

            if not auto_punct and clean_text:
                clean_text = re.sub(r'[.,?!]', '', clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            recognized_words = clean_text.split() if clean_text else []
            chars_to_remove, words_to_type = self.stabilizer.process(recognized_words, force_flush, autocorrect)

            if chars_to_remove > 0 or words_to_type:
                self.inject_text(chars_to_remove, words_to_type)
                    
            if force_flush:
                self.flush_buffers(snapshot_samples)

    def flush_buffers(self, processed_samples):
        with self.buffer_lock:
            del self.audio_buffer[:processed_samples]
        if self.stabilizer.committed_words:
            self.global_context_prompt = " ".join(self.stabilizer.committed_words[-15:])
        self.stabilizer.reset()
        gc.collect()


    def on_close(self):
        self.is_recording = False
        if self.hotkey_listener:
            try: self.hotkey_listener.stop()
            except: pass
        self.stream.stop()
        self.stream.close()
        self.ui.destroy()
        sys.exit(0)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AppCore()
    app.ui.mainloop()