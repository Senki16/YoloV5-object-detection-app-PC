import ctypes
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

import cv2
import torch
import yaml
from PIL import Image, ImageTk


class YOLOWebcamApp:
    BACKGROUND = "#0b2912"
    PANEL = "#122c18"
    ACCENT = "#f2c53d"
    ACCENT_SECONDARY = "#9fc274"
    TEXT = "#f6eed5"
    BORDER = "#183a25"

    def __init__(self, root):
        self.root = root
        self.root.title("Hyrule Guardian Eye")
        self.root.configure(bg=self.BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.geometry("1400x900")

        self.model = None
        self.cap = None
        self.thread = None
        self.running = False
        self.photo = None
        self.last_time = 0
        self.fps = 0
        self.anim_phase = 0
        self.scan_offset = 0
        self.custom_font_name = "Hylia Serif Beta"
        self.font_registered = False

        self.register_custom_font()
        self.create_fonts()
        self.create_widgets()
        self.root.after(60, self.animate_ui)

    def register_custom_font(self):
        font_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "UI",
            "hylia-serif",
            "Hylia Serif Beta v0-009",
            "HyliaSerifBeta-Regular.otf",
        )
        font_path = os.path.abspath(font_path)
        if os.path.isfile(font_path) and os.name == "nt":
            try:
                FR_PRIVATE = 0x10
                result = ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
                self.font_registered = bool(result)
            except Exception:
                self.font_registered = False
        else:
            self.font_registered = False

    def create_fonts(self):
        family = self.custom_font_name if self.font_registered else "Consolas"
        try:
            self.title_font = tkfont.Font(root=self.root, family=family, size=20, weight="bold")
            self.header_font = tkfont.Font(root=self.root, family=family, size=12)
            self.label_font = tkfont.Font(root=self.root, family=family, size=10)
            self.button_font = tkfont.Font(root=self.root, family=family, size=10, weight="bold")
            self.small_font = tkfont.Font(root=self.root, family=family, size=9)
        except tk.TclError:
            self.title_font = tkfont.Font(root=self.root, family="Consolas", size=20, weight="bold")
            self.header_font = tkfont.Font(root=self.root, family="Consolas", size=12)
            self.label_font = tkfont.Font(root=self.root, family="Consolas", size=10)
            self.button_font = tkfont.Font(root=self.root, family="Consolas", size=10, weight="bold")
            self.small_font = tkfont.Font(root=self.root, family="Consolas", size=9)

    def create_widgets(self):
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=1)

        title_frame = tk.Frame(self.root, bg=self.PANEL, bd=2, relief="raised")
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 6))
        title_label = tk.Label(
            title_frame,
            text="HYRULE GUARDIAN EYE",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=self.title_font,
        )
        title_label.pack(padx=12, pady=10)

        header_label = tk.Label(
            title_frame,
            text="Legendary object detection from the Temple of Hyrule",
            bg=self.PANEL,
            fg=self.TEXT,
            font=self.header_font,
        )
        header_label.pack(padx=12, pady=(0, 10))

        scroll_frame = tk.Frame(self.root, bg=self.BACKGROUND)
        scroll_frame.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(12, 6), pady=(0, 12))
        scroll_frame.grid_rowconfigure(0, weight=1)
        scroll_frame.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            scroll_frame,
            bg=self.BACKGROUND,
            highlightthickness=0,
            relief="flat",
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(scroll_frame, command=canvas.yview, bg=self.BORDER, activebackground=self.ACCENT)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.config(yscrollcommand=scrollbar.set)

        controls_panel = tk.Frame(canvas, bg=self.BACKGROUND)
        canvas_window = canvas.create_window(0, 0, window=controls_panel, anchor="nw")

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))

        controls_panel.bind("<Configure>", on_canvas_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        controls_panel.bind("<MouseWheel>", _on_mousewheel)

        controls_panel.grid_columnconfigure(1, weight=1)

        self.create_input_row(controls_panel, "Weights:", 0, "yolov5s.pt", "weights_var")
        self.create_input_row(controls_panel, "Source:", 1, "0", "source_var")
        self.create_input_row(controls_panel, "Confidence:", 2, "0.25", "conf_var", width=8)
        self.create_input_row(controls_panel, "Image size:", 3, "640", "imgsz_var", width=8)

        button_frame = tk.Frame(controls_panel, bg=self.BACKGROUND)
        button_frame.grid(row=4, column=0, columnspan=2, pady=12, sticky="ew")

        self.start_button = tk.Button(
            button_frame,
            text="LAUNCH",
            command=self.start,
            bg=self.ACCENT,
            fg="#0b1e0d",
            activebackground="#f7e28c",
            relief="flat",
            padx=18,
            pady=8,
            font=self.button_font,
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10))

        self.stop_button = tk.Button(
            button_frame,
            text="STOP",
            command=self.stop,
            bg=self.PANEL,
            fg=self.TEXT,
            activebackground="#2d5033",
            relief="flat",
            padx=18,
            pady=8,
            state="disabled",
            font=self.button_font,
        )
        self.stop_button.grid(row=0, column=1)

        self.status_label = tk.Label(
            controls_panel,
            text="STATUS: READY",
            bg=self.BACKGROUND,
            fg=self.ACCENT_SECONDARY,
            anchor="w",
            font=self.button_font,
        )
        self.status_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        custom_panel = tk.Frame(controls_panel, bg=self.PANEL, bd=2, relief="raised")
        custom_panel.grid(row=6, column=0, columnspan=2, sticky="ew", padx=0, pady=(12, 0))
        custom_panel.grid_columnconfigure(1, weight=1)

        tk.Label(
            custom_panel,
            text="CUSTOM CATEGORY TRAINER",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=self.button_font,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))

        self.custom_folder_var = tk.StringVar(value="")
        tk.Button(
            custom_panel,
            text="Select folder",
            command=self.browse_folder,
            bg="#1d2737",
            fg=self.TEXT,
            relief="flat",
            padx=14,
            pady=6,
            font=self.button_font,
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))
        tk.Label(
            custom_panel,
            textvariable=self.custom_folder_var,
            bg=self.PANEL,
            fg=self.TEXT,
            anchor="w",
            justify="left",
            wraplength=300,
            font=self.small_font,
        ).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 6))

        tk.Label(
            custom_panel,
            text="Tag name:",
            bg=self.PANEL,
            fg=self.TEXT,
            font=self.label_font,
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))
        self.custom_tag_var = tk.StringVar(value="televisor")
        tk.Entry(
            custom_panel,
            textvariable=self.custom_tag_var,
            width=20,
            bg=self.BACKGROUND,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.ACCENT,
        ).grid(row=2, column=1, sticky="w", padx=(0, 10), pady=(0, 6))

        self.custom_train_button = tk.Button(
            custom_panel,
            text="Train category",
            command=self.start_custom_training,
            bg=self.ACCENT_SECONDARY,
            fg=self.BACKGROUND,
            activebackground="#c2dd9a",
            relief="flat",
            padx=16,
            pady=8,
            font=self.button_font,
        )
        self.custom_train_button.grid(row=3, column=0, columnspan=2, pady=(0, 10))

        model_panel = tk.Frame(controls_panel, bg=self.PANEL, bd=2, relief="raised")
        model_panel.grid(row=7, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 12))
        model_panel.grid_columnconfigure(1, weight=1)

        tk.Label(
            model_panel,
            text="TRAINED MODELS",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=self.button_font,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))

        tk.Label(
            model_panel,
            text="Select model:",
            bg=self.PANEL,
            fg=self.TEXT,
            font=self.label_font,
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        self.model_selector_var = tk.StringVar(value="yolov5s.pt")
        self.model_selector_combo = tk.OptionMenu(
            model_panel,
            self.model_selector_var,
            "yolov5s.pt",
            command=lambda x: None,
        )
        self.model_selector_combo.config(
            bg=self.BACKGROUND,
            fg=self.TEXT,
            activebackground="#1d2737",
            activeforeground=self.TEXT,
            highlightthickness=0,
        )
        self.model_selector_combo.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 6))

        load_button_frame = tk.Frame(model_panel, bg=self.PANEL)
        load_button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

        self.load_model_button = tk.Button(
            load_button_frame,
            text="Load model",
            command=self.load_selected_model,
            bg=self.ACCENT,
            fg=self.BACKGROUND,
            activebackground="#f7e28c",
            relief="flat",
            padx=14,
            pady=6,
            font=self.button_font,
        )
        self.load_model_button.pack(side="left", padx=(0, 10))

        self.auto_load_var = tk.IntVar(value=1)
        tk.Checkbutton(
            load_button_frame,
            text="Auto-load after training",
            variable=self.auto_load_var,
            bg=self.PANEL,
            fg=self.TEXT,
            selectcolor=self.PANEL,
            activebackground=self.PANEL,
            activeforeground=self.ACCENT,
            font=self.small_font,
        ).pack(side="left")

        self.info_console = tk.Label(
            controls_panel,
            text="FPS: 0 | Objects: 0",
            bg=self.BACKGROUND,
            fg=self.TEXT,
            anchor="w",
            font=self.small_font,
        )
        self.info_console.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self.video_panel = tk.Label(self.root, bg=self.BORDER, bd=2, relief="sunken")
        self.video_panel.grid(row=3, column=0, padx=(12, 6), pady=(0, 12), sticky="nsew")
        self.root.grid_rowconfigure(3, weight=1, minsize=500)

        self.sidebar_panel = tk.Frame(self.root, bg=self.PANEL, bd=2, relief="sunken", width=320)
        self.sidebar_panel.grid(row=3, column=1, padx=(6, 12), pady=(12, 12), sticky="nsew")
        self.sidebar_panel.grid_propagate(False)
        self.sidebar_panel.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        self.sidebar_title = tk.Label(
            self.sidebar_panel,
            text="MISSION HUD",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=self.button_font,
        )
        self.sidebar_title.pack(padx=10, pady=(10, 4), anchor="w")

        self.sidebar_info = tk.Label(
            self.sidebar_panel,
            text="Source: 0\nModel: yolov5s.pt\nStatus: READY",
            justify="left",
            anchor="w",
            width=32,
            wraplength=240,
            bg=self.PANEL,
            fg=self.TEXT,
            font=self.small_font,
        )
        self.sidebar_info.pack(padx=10, pady=(0, 10), anchor="w")

        log_frame = tk.Frame(self.sidebar_panel, bg=self.PANEL)
        log_frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.sidebar_log = tk.Text(
            log_frame,
            width=28,
            height=15,
            wrap="none",
            bg="#08101b",
            fg=self.ACCENT_SECONDARY,
            insertbackground=self.ACCENT_SECONDARY,
            bd=0,
            relief="flat",
            font=self.small_font,
        )
        self.sidebar_log.grid(row=0, column=0, sticky="nsew")
        self.sidebar_log.insert("end", "[00:00] HUD initialized...\n")
        self.sidebar_log.config(state="disabled")

        scrollbar = tk.Scrollbar(
            log_frame, command=self.sidebar_log.yview, bg=self.BORDER, activebackground=self.ACCENT
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.sidebar_log.config(yscrollcommand=scrollbar.set)

        self.refresh_model_selector()

    def create_input_row(self, parent, label_text, row, default, var_name, width=24):
        label = tk.Label(parent, text=label_text, bg=self.BACKGROUND, fg=self.TEXT, font=self.label_font)
        label.grid(row=row, column=0, sticky="w", pady=5)
        var = tk.StringVar(value=default)
        setattr(self, var_name, var)
        entry = tk.Entry(
            parent,
            textvariable=var,
            width=width,
            bg=self.PANEL,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.ACCENT,
            font=self.small_font,
        )
        entry.grid(row=row, column=1, sticky="ew", padx=10)

    def load_model(self):
        weights_path = self.weights_var.get().strip()
        if not weights_path:
            raise ValueError("Please enter the model weights path.")

        if not os.path.isfile(weights_path):
            raise FileNotFoundError(f"Weights file not found: {weights_path}")

        self.status_label.config(text="STATUS: LOADING MODEL...")
        self.root.update_idletasks()

        repo_dir = os.path.dirname(os.path.abspath(__file__))
        self.model = torch.hub.load(repo_dir, "custom", path=weights_path, source="local")
        self.model.conf = float(self.conf_var.get())
        self.model.iou = 0.45
        self.model.to("cpu")

        self.status_label.config(text="STATUS: MODEL LOADED")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with category images")
        if folder:
            self.custom_folder_var.set(folder)
            self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Folder selected: {folder}")

    def refresh_model_selector(self):
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        models = ["yolov5s.pt"]
        unified_model_path = os.path.join(repo_dir, "custom_data", "unified_model_best.pt")
        if os.path.isfile(unified_model_path):
            models.append(f"Unified Custom Model: {unified_model_path}")
        menu = self.model_selector_combo["menu"]
        menu.delete(0, "end")
        for model in models:
            menu.add_command(label=model, command=lambda m=model: self.model_selector_var.set(m))

    def load_selected_model(self):
        selected = self.model_selector_var.get()
        if selected.startswith("custom_"):
            model_path = selected.split(": ", 1)[1] if ": " in selected else selected
        else:
            model_path = selected
        if os.path.isfile(model_path):
            self.weights_var.set(model_path)
            self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Model loaded: {model_path}")
            messagebox.showinfo("Success", f"Model loaded: {os.path.basename(model_path)}")
        else:
            messagebox.showerror("Error", f"Model file not found: {model_path}")

    def append_log(self, text):
        def _append():
            self.sidebar_log.config(state="normal")
            self.sidebar_log.insert("end", text + "\n")
            self.sidebar_log.see("end")
            self.sidebar_log.config(state="disabled")

        self.root.after(0, _append)

    def start_custom_training(self):
        folder = self.custom_folder_var.get().strip()
        tag = self.custom_tag_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid image folder.")
            return
        if not tag:
            messagebox.showerror("Error", "Please enter a category name.")
            return

        self.custom_train_button.config(state="disabled")
        self.status_label.config(text="STATUS: TRAINING CUSTOM CATEGORY")
        self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Starting training for tag: {tag}")

        thread = threading.Thread(target=self.train_custom_category, args=(folder, tag), daemon=True)
        thread.start()

    def prepare_custom_dataset(self, folder, tag):
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        dataset_dir = os.path.join(repo_dir, "custom_data", "unified_model")
        images_train = os.path.join(dataset_dir, "images", "train")
        images_val = os.path.join(dataset_dir, "images", "val")
        labels_train = os.path.join(dataset_dir, "labels", "train")
        labels_val = os.path.join(dataset_dir, "labels", "val")
        for path in (images_train, images_val, labels_train, labels_val):
            os.makedirs(path, exist_ok=True)

        model_info_path = os.path.join(repo_dir, "custom_data", "model_info.yaml")
        if os.path.isfile(model_info_path):
            with open(model_info_path, encoding="utf-8") as f:
                model_info = yaml.safe_load(f) or {}
        else:
            model_info = {}

        existing_classes = model_info.get("classes", [])
        if tag not in existing_classes:
            existing_classes.append(tag)
        model_info["classes"] = existing_classes

        with open(model_info_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(model_info, f, sort_keys=False)

        class_idx = existing_classes.index(tag)
        new_image_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))
        ]
        if not new_image_files:
            raise ValueError("No images found in the selected folder.")

        random.seed(42)
        random.shuffle(new_image_files)
        split = max(1, int(len(new_image_files) * 0.8))
        train_files = new_image_files[:split]
        val_files = new_image_files[split:] or train_files[:1]

        for image_paths, image_dest, label_dest in (
            (train_files, images_train, labels_train),
            (val_files, images_val, labels_val),
        ):
            for src_path in image_paths:
                base_name = os.path.basename(src_path)
                dst_path = os.path.join(image_dest, f"{tag}_{base_name}")
                shutil.copy2(src_path, dst_path)
                label_path = os.path.join(label_dest, os.path.splitext(f"{tag}_{base_name}")[0] + ".txt")
                with open(label_path, "w", encoding="utf-8") as f:
                    f.write(f"{class_idx} 0.5 0.5 0.95 0.95\n")

        data_yaml = os.path.join(dataset_dir, "data.yaml")
        with open(data_yaml, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "train": os.path.abspath(images_train),
                    "val": os.path.abspath(images_val),
                    "nc": len(existing_classes),
                    "names": existing_classes,
                },
                f,
                sort_keys=False,
            )
        return data_yaml

    def train_custom_category(self, folder, tag):
        try:
            data_yaml = self.prepare_custom_dataset(folder, tag)
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            weights_path = self.weights_var.get().strip() or os.path.join(repo_dir, "yolov5s.pt")
            save_name = f"custom_{tag}"
            command = [
                sys.executable,
                os.path.join(repo_dir, "train.py"),
                "--imgsz",
                self.imgsz_var.get(),
                "--batch",
                "8",
                "--epochs",
                "5",
                "--data",
                data_yaml,
                "--weights",
                weights_path,
                "--name",
                save_name,
                "--exist-ok",
            ]
            self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Training command: {' '.join(command)}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            for line in process.stdout:
                self.append_log(line.rstrip())
            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"Training failed with exit code {process.returncode}")

            best_weights = os.path.join(repo_dir, "runs", "train", save_name, "weights", "best.pt")
            unified_weights = os.path.join(repo_dir, "custom_data", "unified_model_best.pt")
            if os.path.isfile(best_weights):
                shutil.copy2(best_weights, unified_weights)
                self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Training complete. Unified model: {unified_weights}")
                self.root.after(0, self.refresh_model_selector)
                if self.auto_load_var.get():
                    self.weights_var.set(unified_weights)
                    self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Auto-loading unified model: {unified_weights}")
            else:
                self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Training complete, but best weights not found.")
        except Exception as e:
            self.append_log(f"[ {time.strftime('%H:%M:%S')} ] Error: {e}")
        finally:
            self.root.after(0, lambda: self.custom_train_button.config(state="normal"))
            self.root.after(0, lambda: self.status_label.config(text="STATUS: READY"))

    def start(self):
        if self.running:
            return

        try:
            if self.model is None:
                self.load_model()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        source_text = self.source_var.get().strip()
        source = int(source_text) if source_text.isdigit() else source_text

        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Cannot open source: {source_text}")
            return

        self.running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text="STATUS: STREAMING")
        self.last_time = time.time()

        self.thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="STATUS: STOPPED")

    def draw_boxes(self, frame, results):
        detections = results.xyxy[0].cpu().numpy()
        for *box, conf, cls in detections:
            x1, y1, x2, y2 = map(int, box)
            label = f"{results.names[int(cls)]}: {conf:.2f}"
            color = (56, 255, 146)
            line_thickness = max(2, int(frame.shape[1] / 300))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, line_thickness)
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.65
            thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            y_text = y1 - 14 if y1 - 14 > text_height else y1 + text_height + 14
            cv2.rectangle(
                frame, (x1, y_text - text_height - 6), (x1 + text_width + 6, y_text + baseline - 6), (20, 25, 45), -1
            )
            cv2.putText(frame, label, (x1 + 3, y_text - 6), font, font_scale, (235, 245, 255), thickness, cv2.LINE_AA)
        return frame

    def capture_loop(self):
        imgsz = int(self.imgsz_var.get())
        while self.running:
            success, frame = self.cap.read()
            if not success or frame is None:
                self.status_label.config(text="STATUS: ERROR READING FRAME")
                break

            try:
                results = self.model(frame, size=imgsz)
                frame = self.draw_boxes(frame, results)
                frame = self.draw_hud_overlay(frame)
                count = len(results.xyxy[0])
                detected_names = [results.names[int(cls)] for *_, cls in results.xyxy[0].cpu().numpy()]
            except Exception as e:
                self.status_label.config(text="STATUS: INFERENCE ERROR")
                print(e)
                break

            current_time = time.time()
            self.fps = 1.0 / (current_time - self.last_time) if current_time != self.last_time else self.fps
            self.last_time = current_time

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image=image)
            self.root.after(0, self.update_frame, photo, count, detected_names)
            time.sleep(0.02)

        self.running = False
        if self.cap is not None:
            self.cap.release()
        self.root.after(0, self.on_stream_end)

    def update_frame(self, photo, count, detected_names):
        self.photo = photo
        self.video_panel.config(image=self.photo)
        self.info_console.config(text=f"FPS: {self.fps:.1f} | Objects detected: {count}")
        self.update_sidebar(count, detected_names)

    def update_sidebar(self, count, detected_names):
        status_text = (
            f"Source: {self.source_var.get()}\n"
            f"Model: {self.weights_var.get()}\n"
            f"Status: {'STREAMING' if self.running else 'READY'}\n"
            f"FPS: {self.fps:.1f}\n"
            f"Objects: {count}\n"
            f"Detected: {', '.join(detected_names[:5]) if detected_names else 'None'}"
        )
        self.sidebar_info.config(text=status_text)

        log_text = f"[{time.strftime('%H:%M:%S')}] Detected {count} object(s)\n"
        if detected_names:
            log_text += f"    Classes: {', '.join(detected_names[:5])}\n"

        self.sidebar_log.config(state="normal")
        self.sidebar_log.insert("end", log_text)
        self.sidebar_log.see("end")
        self.sidebar_log.config(state="disabled")

    def animate_ui(self):
        self.anim_phase = (self.anim_phase + 1) % 100
        pulse = (1 + math.sin(self.anim_phase * 0.12)) / 2
        r = int(56 + pulse * 120)
        g = int(255 - pulse * 20)
        b = int(146 + pulse * 50)
        accent = f"#{r:02x}{g:02x}{b:02x}"

        self.start_button.config(bg=accent, activebackground="#7effba")
        self.status_label.config(fg=accent)
        if self.running:
            dots = (self.anim_phase // 20) % 4
            self.status_label.config(text=f"STATUS: STREAMING {' .' * dots}")

        self.root.after(60, self.animate_ui)

    def draw_hud_overlay(self, frame):
        overlay = frame.copy()
        h, w = frame.shape[:2]
        line_color = (18, 82, 105)
        for x in range(0, w, 120):
            cv2.line(overlay, (x, 0), (x, h), line_color, 1)
        for y in range(0, h, 90):
            cv2.line(overlay, (0, y), (w, y), line_color, 1)

        scan_y = self.scan_offset % (2 * h)
        scan_y = scan_y if scan_y < h else 2 * h - scan_y
        cv2.line(overlay, (0, scan_y), (w, scan_y), (68, 255, 178), 2)
        self.scan_offset = (self.scan_offset + 4) % (2 * h)

        cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)

        cv2.putText(
            frame, "SYSTEM CHECK: ONLINE", (16, 34), cv2.FONT_HERSHEY_DUPLEX, 0.7, (92, 255, 178), 1, cv2.LINE_AA
        )
        cv2.putText(frame, "EDGE MODE: ACTIVE", (16, 60), cv2.FONT_HERSHEY_DUPLEX, 0.6, (163, 255, 210), 1, cv2.LINE_AA)

        return frame

    def on_stream_end(self):
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="STATUS: STOPPED")

    def on_close(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()


def main():
    root = tk.Tk()
    root.geometry("1400x900")
    YOLOWebcamApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
