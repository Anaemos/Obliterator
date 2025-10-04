#!/usr/bin/env python3
# obliterator_gui_integrated.py - (Version 12.3 - Integrated Backend & Viewer)
# GUI for the Obliterator Secure Wipe Tool
# Integrated certificate backend and viewer functionality

import tkinter
import customtkinter
import subprocess
import json
import datetime
import os
import threading
import time
import sys
from queue import Queue, Empty

# --- Pillow library for image support ---
from PIL import Image, ImageTk

# --- Backend Integration ---
try:
    from certificate_backend_integration import CertificateBackendClient, SupabaseAuth
    HAS_BACKEND_INTEGRATION = True
except ImportError:
    HAS_BACKEND_INTEGRATION = False
    print("⚠️  Backend integration module not available - PDF generation disabled")

# --- Certificate Viewer ---
try:
    from certificate_viewer_addon import CertificateViewerFrame
    HAS_CERT_VIEWER = True
except ImportError:
    HAS_CERT_VIEWER = False
    print("⚠️  Certificate viewer module not available - viewer disabled")

# --- AUTHENTICATION INTEGRATION ---
def check_authentication():
    """Check if user is authenticated by running login system"""
    login_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obliterator_login")
    login_script = os.path.join(login_dir, "login_system.py")
    
    if os.path.exists(login_script):
        print("Authentication required. Launching login system...")
        try:
            result = subprocess.run([sys.executable, login_script], 
                                  cwd=login_dir, 
                                  capture_output=False)
            
            if result.returncode == 0:
                print("Authentication successful!")
                return True
            else:
                print("Authentication failed or cancelled.")
                return False
        except Exception as e:
            print(f"Error running authentication: {e}")
            return False
    else:
        print("Warning: Login system not found. Running without authentication.")
        return True

# --- Configuration ---
APP_NAME = "OBLITERATOR"
APP_VERSION = "12.3-integrated"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THEME_FILE = os.path.join(SCRIPT_DIR, "purple_theme.json")
LOGO_FILE = os.path.join(SCRIPT_DIR, "logo.png") 
CERT_DIR = os.path.join(SCRIPT_DIR, "certificates/")
WIPE_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "wipe_disk.sh")
DEVICE_DETECTION_SCRIPT = os.path.join(SCRIPT_DIR, "detect_devices.sh")
CERT_GENERATOR_PATH = os.path.join(SCRIPT_DIR, "generate_certificate.sh")

# --- Supabase Configuration (for backend) ---
SUPABASE_URL = "https://ajqmxtjlxplnbofwoxtf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFqcW14dGpseHBsbmJvZndveHRmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgzNzMzMjEsImV4cCI6MjA3Mzk0OTMyMX0.m9C9chwlriwRojINYQrWSo96wyJTKOQONkqsi8-xsBQ"

# --- Font Definitions ---
FONT_HEADER = ("Roboto", 42, "bold")
FONT_SUBHEADER = ("Roboto", 24, "bold")
FONT_BODY_BOLD = ("Roboto", 18, "bold")
FONT_BODY = ("Roboto", 16)
FONT_MONO = ("monospace", 14)

class CustomTextbox(customtkinter.CTkTextbox):
    def __init__(self, *args, scrollbar_button_color=None, **kwargs):
        super().__init__(*args, **kwargs)
        if scrollbar_button_color is not None:
            if hasattr(self, '_v_scrollbar') and self._v_scrollbar is not None:
                self._v_scrollbar.configure(button_color=scrollbar_button_color)
            if hasattr(self, '_h_scrollbar') and self._h_scrollbar is not None:
                self._h_scrollbar.configure(button_color=scrollbar_button_color)

# --- Main Application Controller ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        customtkinter.set_appearance_mode("Dark")
        if os.path.exists(THEME_FILE): customtkinter.set_default_color_theme(THEME_FILE)
        else: print(f"Warning: Theme file not found at {THEME_FILE}.")
        
        self.title(APP_NAME)
        self.geometry("1920x1080")
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)

        self.container = customtkinter.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1); self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.devices_to_wipe = []

        for F in (SplashFrame, MainFrame, ConfirmationFrame, WipeProgressFrame, CompletionFrame):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(SplashFrame)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()
        if hasattr(frame, 'on_show'): frame.on_show()

    def start_wipe_process(self, devices):
        """Show confirmation screen - does NOT execute wipe yet"""
        print(f"DEBUG: start_wipe_process called with {len(devices)} devices")
        print("DEBUG: Showing ConfirmationFrame (NOT starting wipe)")
        self.devices_to_wipe = devices
        self.frames[ConfirmationFrame].update_device_info(devices)
        self.show_frame(ConfirmationFrame)

    def execute_wipe(self):
        """ACTUALLY start the wipe process - only called after confirmation"""
        print(f"DEBUG: execute_wipe called - STARTING ACTUAL WIPE of {len(self.devices_to_wipe)} devices")
        self.frames[WipeProgressFrame].start_wipe_queue(self.devices_to_wipe)
        self.show_frame(WipeProgressFrame)

    def show_completion(self, wiped_devices):
        self.frames[CompletionFrame].update_completion_info(wiped_devices)
        self.show_frame(CompletionFrame)

# --- Splash Screen Frame ---
class SplashFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        try:
            self.logo_image = customtkinter.CTkImage(Image.open(LOGO_FILE), size=(350, 350))
            logo_label = customtkinter.CTkLabel(self, image=self.logo_image, text="")
            logo_label.pack(pady=(100, 20))
        except FileNotFoundError:
            logo_label = customtkinter.CTkLabel(self, text="🛡️", font=("Roboto", 100))
            logo_label.pack(pady=(100, 20))

        self.name_label = customtkinter.CTkLabel(self, text=APP_NAME, font=FONT_HEADER)
        self.name_label.pack(pady=10, padx=20)
        self.progress_bar = customtkinter.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.pack(pady=20, padx=100, fill="x")

    def on_show(self):
        self.progress_bar.start()
        self.after(3000, lambda: self.controller.show_frame(MainFrame))

# --- Main Application Frame ---
class MainFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.device_checkboxes = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=2)
        self.grid_rowconfigure(3, weight=0)
        
        # --- Header ---
        header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=(10, 0), padx=20, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_label = customtkinter.CTkLabel(header_frame, text=APP_NAME, font=FONT_HEADER)
        header_label.grid(row=0, column=0, pady=10)

        # --- Drive Selection ---
        drive_list_frame = customtkinter.CTkFrame(self)
        drive_list_frame.grid(row=1, column=0, pady=10, padx=20, sticky="nsew")
        drive_list_frame.grid_columnconfigure(0, weight=1); drive_list_frame.grid_rowconfigure(1, weight=1)
        
        drive_list_header = customtkinter.CTkLabel(drive_list_frame, text="1. Select Drives to Wipe", font=FONT_BODY_BOLD)
        drive_list_header.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        self.scrollable_drive_list = customtkinter.CTkScrollableFrame(drive_list_frame)
        self.scrollable_drive_list.grid(row=1, column=0, pady=5, padx=10, sticky="nsew")

        # --- Details Container ---
        details_container = customtkinter.CTkFrame(self, fg_color="transparent")
        details_container.grid(row=2, column=0, pady=10, padx=20, sticky="nsew")
        details_container.grid_columnconfigure((0, 1), weight=1)
        details_container.grid_rowconfigure(0, weight=1)

        # --- Drive Details Box ---
        drive_details_frame = customtkinter.CTkFrame(details_container)
        drive_details_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        drive_details_frame.grid_columnconfigure(0, weight=1); drive_details_frame.grid_rowconfigure(1, weight=1)
        drive_details_header = customtkinter.CTkLabel(drive_details_frame, text="Drive Details & Sanitization Plan", font=FONT_BODY_BOLD)
        drive_details_header.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        self.details_textbox = CustomTextbox(drive_details_frame, state="disabled", font=FONT_MONO, scrollbar_button_color="#FFD700")
        self.details_textbox.grid(row=1, column=0, pady=5, padx=10, sticky="nsew")

        # --- Host System Box ---
        host_details_frame = customtkinter.CTkFrame(details_container)
        host_details_frame.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        host_details_frame.grid_columnconfigure(0, weight=1); host_details_frame.grid_rowconfigure(1, weight=1)
        host_header = customtkinter.CTkLabel(host_details_frame, text="Host System Information", font=FONT_BODY_BOLD)
        host_header.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        self.host_details_textbox = CustomTextbox(host_details_frame, state="disabled", font=FONT_MONO, scrollbar_button_color="#FFD700")
        self.host_details_textbox.grid(row=1, column=0, pady=5, padx=10, sticky="nsew")
        
        # --- Footer ---
        footer_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=3, column=0, pady=20, padx=20, sticky="e")
        self.wipe_button = customtkinter.CTkButton(footer_frame, text="Proceed to Final Confirmation...", font=FONT_BODY, state="disabled", 
                                                 fg_color="#8B0000", hover_color="#A52A2A",
                                                 command=self.confirm_wipe)
        self.wipe_button.pack()
    
    def on_show(self):
        self.populate_devices()
        self.display_host_system_info()

    def get_host_system_info(self):
        details = {}
        try:
            details['manufacturer'] = subprocess.check_output(['dmidecode', '-s', 'system-manufacturer']).decode().strip()
            details['model'] = subprocess.check_output(['dmidecode', '-s', 'system-product-name']).decode().strip()
            details['serial'] = subprocess.check_output(['dmidecode', '-s', 'system-serial-number']).decode().strip()
        except Exception as e: 
            print(f"Could not get host info: {e}")
        return details

    def display_host_system_info(self):
        host_info = self.get_host_system_info()
        info_text = ( "This is the machine performing the wipe.\n" + ("-"*40) + "\n"
                      f"Manufacturer: {host_info.get('manufacturer', 'N/A')}\n"
                      f"Model:        {host_info.get('model', 'N/A')}\n"
                      f"Serial:       {host_info.get('serial', 'N/A')}\n\n"
                      f"Media Source: This Live USB Environment\n" )
        self.host_details_textbox.configure(state="normal")
        self.host_details_textbox.delete("1.0", "end")
        self.host_details_textbox.insert("1.0", info_text)
        self.host_details_textbox.configure(state="disabled")

    def get_drive_details(self, dev_path):
        """Get detailed drive information with proper error handling"""
        print(f"Getting drive details for {dev_path}")
        
        if os.path.exists(DEVICE_DETECTION_SCRIPT) and os.access(DEVICE_DETECTION_SCRIPT, os.X_OK):
            try:
                print(f"Trying enhanced detection for {dev_path}")
                result = subprocess.run([
                    'bash', DEVICE_DETECTION_SCRIPT, 
                    '--json', '--device', dev_path
                ], capture_output=True, text=True, check=True, timeout=30)
                
                detection_data = json.loads(result.stdout)
                devices = detection_data.get('devices', [])
                
                if devices:
                    device_info = devices[0]
                    print(f"Enhanced detection successful for {dev_path}")
                    return {
                        'model': device_info.get('model', 'N/A'),
                        'serial_number': device_info.get('serial_number', 'N/A'),
                        'size_bytes': device_info.get('size_bytes', 0),
                        'device_type': device_info.get('device_type', 'unknown'),
                        'recommended_method': device_info.get('recommended_method', 'overwrite'),
                        'estimated_time': device_info.get('estimated_time_minutes', 60),
                        'warnings': device_info.get('warnings', ''),
                        'has_hpa': device_info.get('has_hpa', False),
                        'has_dco': device_info.get('has_dco', False),
                        'smart_health': device_info.get('smart_health', 'unknown')
                    }
                else:
                    print(f"Enhanced detection returned no devices for {dev_path}")
            except subprocess.TimeoutExpired:
                print(f"Enhanced detection timed out for {dev_path}")
            except subprocess.CalledProcessError as e:
                print(f"Enhanced detection failed for {dev_path} with exit code {e.returncode}")
                print(f"stderr: {e.stderr}")
            except json.JSONDecodeError as e:
                print(f"Enhanced detection returned invalid JSON for {dev_path}: {e}")
            except Exception as e:
                print(f"Enhanced detection error for {dev_path}: {e}")
        else:
            print(f"Enhanced detection script not found or not executable: {DEVICE_DETECTION_SCRIPT}")
            
        print(f"Falling back to basic detection for {dev_path}")
        try:
            result = subprocess.run(['smartctl', '-i', '--json', dev_path], 
                                  capture_output=True, text=True, check=True, timeout=15)
            data = json.loads(result.stdout)
            print(f"Basic detection successful for {dev_path}")
            return {
                'model': data.get('model_name', 'N/A'), 
                'serial_number': data.get('serial_number', 'N/A'), 
                'size_bytes': data.get('user_capacity', {}).get('bytes', 0),
                'device_type': 'unknown',
                'recommended_method': 'overwrite_5pass',
                'estimated_time': 120,
                'warnings': 'Enhanced detection unavailable - using basic info',
                'has_hpa': False,
                'has_dco': False,
                'smart_health': 'unknown'
            }
        except Exception as e:
            print(f"Basic detection also failed for {dev_path}: {e}")
            return {
                'model': 'N/A', 
                'serial_number': 'N/A', 
                'size_bytes': 0,
                'device_type': 'unknown',
                'recommended_method': 'overwrite_5pass',
                'estimated_time': 120,
                'warnings': 'Device information unavailable',
                'has_hpa': False,
                'has_dco': False,
                'smart_health': 'unknown'
            }

    def populate_devices(self):
        for checkbox in self.device_checkboxes.values(): 
            checkbox.destroy()
        self.device_checkboxes.clear()
        
        try:
            result = subprocess.run(['lsblk', '-d', '--json', '-o', 'NAME,MODEL,SERIAL,SIZE,TYPE'], 
                                  capture_output=True, text=True, check=True, timeout=10)
            devices = [dev for dev in json.loads(result.stdout).get("blockdevices", []) 
                      if dev.get("type") in ["disk", "nvme"]]
        except Exception as e:
            print(f"Error getting device list: {e}")
            devices = []
            
        for dev in devices:
            dev_path = f"/dev/{dev.get('name', 'N/A')}"
            display_text = f"💾 {dev_path}  ({dev.get('size', 'N/A')})"
            var = tkinter.BooleanVar()
            checkbox = customtkinter.CTkCheckBox(self.scrollable_drive_list, text=display_text, 
                                               variable=var, font=FONT_BODY, command=self.update_selection_status)
            checkbox.pack(anchor="w", padx=10, pady=5)
            self.device_checkboxes[dev_path] = {"var": var, "data": dev}
        self.update_selection_status()

    def update_selection_status(self):
        selected_devs_data = [info["data"] for path, info in self.device_checkboxes.items() if info["var"].get()]
        self.wipe_button.configure(state="normal" if selected_devs_data else "disabled")
        self.display_drive_details(selected_devs_data)

    def display_drive_details(self, selected_devs):
        self.details_textbox.configure(state="normal")
        self.details_textbox.delete("1.0", "end")
        
        if not selected_devs:
            self.details_textbox.insert("1.0", "Select one or more drives to see the sanitization plan.")
        else:
            plan_text = f"Tool Used:   {APP_NAME} v{APP_VERSION}\n"
            plan_text += f"Standard:    NIST SP 800-88r2 Compliant\n"
            plan_text += ("-"*50) + "\n\n"
            
            total_estimated_time = 0
            
            for dev_data in selected_devs:
                dev_path = f"/dev/{dev_data.get('name')}"
                scraped = self.get_drive_details(dev_path)
                
                device_type = scraped.get('device_type', 'unknown')
                recommended_method = scraped.get('recommended_method', 'overwrite')
                estimated_time = scraped.get('estimated_time', 60)
                warnings = scraped.get('warnings', '')
                
                total_estimated_time += estimated_time
                
                plan_text += f"Target: {dev_path}\n"
                plan_text += f"  Model:           {scraped.get('model', 'N/A')}\n"
                plan_text += f"  Serial:          {scraped.get('serial_number', 'N/A')}\n"
                plan_text += f"  Type:            {device_type}\n"
                plan_text += f"  Method:          {recommended_method}\n"
                plan_text += f"  Est. Time:       {estimated_time} minutes\n"
                plan_text += f"  SMART Health:    {scraped.get('smart_health', 'unknown')}\n"
                
                security_info = []
                if scraped.get('has_hpa'):
                    security_info.append("HPA detected")
                if scraped.get('has_dco'):
                    security_info.append("DCO detected")
                
                if security_info:
                    plan_text += f"  Security:        {', '.join(security_info)}\n"
                
                if warnings:
                    plan_text += f"  Warnings:        {warnings}\n"
                
                plan_text += "\n"
            
            plan_text += ("-"*50) + "\n"
            plan_text += f"Total Devices:     {len(selected_devs)}\n"
            plan_text += f"Total Est. Time:   {total_estimated_time} minutes ({total_estimated_time//60}h {total_estimated_time%60}m)\n"
            plan_text += f"Compliance:        NIST SP 800-88r2\n"
            
            self.details_textbox.insert("1.0", plan_text)
        self.details_textbox.configure(state="disabled")

    def confirm_wipe(self):
        """Navigate to confirmation screen - does NOT start wipe"""
        selected_devices = [info["data"] for path, info in self.device_checkboxes.items() if info["var"].get()]
        print(f"DEBUG: Moving to confirmation screen for {len(selected_devices)} devices")
        self.controller.start_wipe_process(selected_devices)

class ConfirmationFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.main_label = customtkinter.CTkLabel(self, text="⚠️ FINAL CONFIRMATION ⚠️", font=FONT_HEADER, text_color="orange")
        self.main_label.pack(pady=(200, 20))
        self.info_label = customtkinter.CTkLabel(self, text="", font=FONT_BODY, wraplength=500)
        self.info_label.pack(pady=10, padx=20)
        self.instruction_label = customtkinter.CTkLabel(self, text="Type 'OBLITERATE' below to proceed.", font=FONT_BODY)
        self.instruction_label.pack(pady=20)
        self.entry = customtkinter.CTkEntry(self, width=300, font=FONT_SUBHEADER)
        self.entry.pack()
        self.entry.bind("<KeyRelease>", self.check_token)
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=40)
        self.confirm_button = customtkinter.CTkButton(button_frame, text="Confirm and Wipe", font=FONT_BODY, state="disabled",
                                                      fg_color="#8B0000", hover_color="#A52A2A",
                                                      command=self.controller.execute_wipe)
        self.confirm_button.pack(side="left", padx=10)
        cancel_button = customtkinter.CTkButton(button_frame, text="Cancel", font=FONT_BODY, 
                                              command=lambda: self.controller.show_frame(MainFrame))
        cancel_button.pack(side="right", padx=10)
        
    def update_device_info(self, devices):
        info_text = f"You are about to permanently destroy all data on {len(devices)} device(s):\n\n"
        for dev in devices[:3]: 
            info_text += f"- /dev/{dev.get('name')} ({dev.get('model') or 'N/A'})\n"
        if len(devices) > 3: 
            info_text += f"...and {len(devices)-3} more."
        self.info_label.configure(text=info_text)
        self.entry.delete(0, "end")
        self.check_token(None)
        
    def check_token(self, event):
        """Enable confirm button only when 'OBLITERATE' is typed"""
        is_correct = self.entry.get() == "OBLITERATE"
        self.confirm_button.configure(state="normal" if is_correct else "disabled")
        if is_correct:
            print("DEBUG: Confirmation token 'OBLITERATE' entered - button enabled")
        return is_correct

class WipeProgressFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.process, self.start_time = None, 0
        self.device_queue, self.current_device_index, self.total_devices = [], 0, 0
        self.current_device_total_size = 0
        self.wiped_devices = []
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        center_frame = customtkinter.CTkFrame(self)
        center_frame.grid(row=0, column=0)
        
        self.overall_title_label = customtkinter.CTkLabel(center_frame, text="", font=FONT_SUBHEADER)
        self.overall_title_label.pack(pady=(20, 0), padx=50)
        self.title_label = customtkinter.CTkLabel(center_frame, text="Wiping Drive...", font=FONT_BODY_BOLD)
        self.title_label.pack(pady=(0,20), padx=50)
        self.progress_label = customtkinter.CTkLabel(center_frame, text="Status: Initializing...", font=FONT_BODY)
        self.progress_label.pack(pady=10, padx=20)
        self.progress_bar = customtkinter.CTkProgressBar(center_frame, width=500)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10, padx=20)
        
        info_frame = customtkinter.CTkFrame(center_frame, fg_color="transparent")
        info_frame.pack(pady=20, padx=20, fill="x")
        info_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.time_label = customtkinter.CTkLabel(info_frame, text="Elapsed: 00:00:00", font=FONT_MONO)
        self.time_label.grid(row=0, column=0, sticky="w")

        
        self.log_textbox = CustomTextbox(center_frame, height=250, width=600, state="disabled", 
                                       font=FONT_MONO, scrollbar_button_color="#FFD700")
        self.log_textbox.pack(pady=10, padx=20)
        
    def log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def start_wipe_queue(self, devices):
        """Initialize the wipe queue - CRITICAL: Only call after user confirmation"""
        if not devices:
            print("ERROR: start_wipe_queue called with no devices!")
            return
            
        print(f"DEBUG: start_wipe_queue called with {len(devices)} devices")
        print("DEBUG: ⚠️ WIPE PROCESS STARTING - THIS SHOULD ONLY HAPPEN AFTER CONFIRMATION")
        
        self.device_queue = list(devices)
        self.current_device_index, self.total_devices = 0, len(devices)
        self.wiped_devices = []
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        self.log(f"⚠️ WIPE PROCESS INITIALIZED - {len(devices)} device(s) queued")
        self.process_next_in_queue()
        
    def process_next_in_queue(self):
        if not self.device_queue:
            self.overall_title_label.configure(text="All Wipes Complete!")
            self.log("✅ All selected drives have been processed.")
            self.controller.show_completion(self.wiped_devices)
            return
            
        self.current_device_index += 1
        device_data = self.device_queue.pop(0)
        scraped_info = self.controller.frames[MainFrame].get_drive_details(f"/dev/{device_data['name']}")
        self.progress_bar.set(0)
        self.overall_title_label.configure(text=f"Processing Drive {self.current_device_index} of {self.total_devices}")
        self.title_label.configure(text=f"Wiping /dev/{device_data['name']} ({device_data['size']})")
        self.log("\n" + ("-"*50) + f"\nStarting wipe for /dev/{device_data['name']}\n" + ("-"*50))
        threading.Thread(target=self.run_wipe_script, args=(device_data,), daemon=True).start()
        
    def run_wipe_script(self, device_data):
        self.start_time = time.time()
        self.after(1000, self.update_timer)
        device_path = f"/dev/{device_data['name']}"
        
        if os.path.exists(WIPE_SCRIPT_PATH) and os.access(WIPE_SCRIPT_PATH, os.X_OK):
            command = ['bash', WIPE_SCRIPT_PATH, device_path, 'OBLITERATE']
            self.log(f"Using enhanced wipe script: {WIPE_SCRIPT_PATH}")
        else:
            basic_wipe_script = os.path.join(SCRIPT_DIR, "wipe_disk.sh")
            if os.path.exists(basic_wipe_script) and os.access(basic_wipe_script, os.X_OK):
                command = ['bash', basic_wipe_script, device_path, 'OBLITERATE']
                self.log(f"Using basic wipe script: {basic_wipe_script}")
            else:
                self.log("ERROR: No wipe script found!")
                self.wipe_finished(False, device_data)
                return
                
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                          text=True, bufsize=1)
            q_out, q_err = Queue(), Queue()
            threading.Thread(target=self.read_stream, args=(self.process.stdout, q_out), daemon=True).start()
            threading.Thread(target=self.read_stream, args=(self.process.stderr, q_err), daemon=True).start()
            self.after(100, self.check_queues, q_out, q_err, device_data)
        except Exception as e: 
            self.log(f"CRITICAL FAILURE: {e}")
            self.wipe_finished(False, device_data)
            
    def read_stream(self, stream, queue):
        try:
            for line in iter(stream.readline, ''): 
                queue.put(line)
        except Exception as e:
            queue.put(f"ERROR reading stream: {e}\n")
            
    def check_queues(self, q_out, q_err, device_data):
        try:
            while True:
                line = q_out.get_nowait().strip()
                if line:
                    self.log(f"OUT: {line}")
                    
                    if line.startswith("PROGRESS:"):
                        self.update_progress_from_line(line)
                    elif line.startswith("DEVICE_TYPE:"):
                        device_type = line.split(":", 1)[1] if ":" in line else "unknown"
                        self.log(f"Device type detected: {device_type}")
                    elif line.startswith("SANITIZE_METHOD:"):
                        method = line.split(":", 1)[1] if ":" in line else "unknown"
                        self.progress_label.configure(text=f"Status: Using {method} method")
                    elif line.startswith("HPA_DETECTED:"):
                        hpa_status = line.split(":", 1)[1] if ":" in line else "unknown"
                        if hpa_status == "true":
                            self.log("HPA (Hidden Protected Area) detected and will be removed")
                    elif line.startswith("ATA_SECURITY:"):
                        security_info = line.split(":", 1)[1] if ":" in line else ""
                        self.log(f"ATA Security: {security_info}")
                    elif line.startswith("VERIFICATION:"):
                        verification_msg = line.split(":", 1)[1] if ":" in line else ""
                        self.progress_label.configure(text=f"Status: {verification_msg}")
                    elif "STATUS:SUCCESS" in line: 
                        self.wipe_finished(True, device_data)
                        return
                    elif "STATUS:FAILED" in line:
                        self.wipe_finished(False, device_data)
                        return
        except Empty: 
            pass
            
        try:
            while True:
                line = q_err.get_nowait().strip()
                if line:
                    if "[INFO]" in line or "[WARN]" in line or "[ERROR]" in line:
                        self.log(f"LOG: {line}")
                    elif "MiB/s" in line or "GiB/s" in line:
                        parts = line.split()
                        try:
                            if len(parts) >= 2:
                                wiped_raw = parts[0]
                                speed = parts[-1].strip("[]")
                                wiped_bytes = 0
                                
                                if wiped_raw.endswith("GiB"): 
                                    wiped_bytes = float(wiped_raw[:-3]) * (1024**3)
                                elif wiped_raw.endswith("MiB"): 
                                    wiped_bytes = float(wiped_raw[:-3]) * (1024**2)
                                elif wiped_raw.endswith("KiB"): 
                                    wiped_bytes = float(wiped_raw[:-3]) * 1024
                                
                                self.data_label.configure(
                                    text=f"Wiped: {self.bytes_to_gib_str(wiped_bytes)} / {self.bytes_to_gib_str(self.current_device_total_size)}")
                        except (IndexError, ValueError, AttributeError): 
                            pass
                    elif "%" in line and ("ETA" in line or "elapsed" in line):
                        self.log(f"PROGRESS: {line}")
                    else: 
                        self.log(f"ERR: {line}")
        except Empty: 
            pass
            
        if self.process and self.process.poll() is None: 
            self.after(100, self.check_queues, q_out, q_err, device_data)
        elif self.process and self.process.returncode != 0: 
            self.wipe_finished(False, device_data)
            
    def bytes_to_gib_str(self, num_bytes):
        if num_bytes == 0: 
            return "0.00 GiB"
        return f"{num_bytes / (1024**3):.2f} GiB"
        
    def update_progress_from_line(self, line):
        try:
            parts = line.split(':')
            if len(parts) >= 3:
                progress_part = parts[1]
                status_message = parts[2]
                
                if '/' in progress_part:
                    current_pass, total_passes = map(int, progress_part.split('/'))
                    self.progress_bar.set(float(current_pass) / float(total_passes))
                    self.progress_label.configure(text=f"Status: Pass {current_pass}/{total_passes} - {status_message}")
        except (IndexError, ValueError, AttributeError): 
            pass
            
    def wipe_finished(self, success, device_data):
        self.progress_bar.set(1.0)
        if success:
            self.progress_label.configure(text="Status: Wipe and Verification Complete!")
            self.log(f"✅ WIPE SUCCESSFUL for /dev/{device_data['name']}")
            scraped_info = self.controller.frames[MainFrame].get_drive_details(f"/dev/{device_data['name']}")
            device_info = {
                'name': device_data['name'],
                'model': device_data.get('model', 'N/A'),
                'size': device_data.get('size', 'N/A'),
                'serial_number': scraped_info.get('serial_number', 'UNKNOWN_SERIAL')
            }
            self.wiped_devices.append(device_info)
        else:
            self.progress_label.configure(text="Status: WIPE FAILED!", text_color="red")
            self.log(f"❌ WIPE FAILED for /dev/{device_data['name']}. Halting queue.")
            self.device_queue.clear()
        self.process_next_in_queue()
            
    def update_timer(self):
        if self.process and self.process.poll() is None:
            elapsed = time.time() - self.start_time
            self.time_label.configure(text=f"Elapsed: {str(datetime.timedelta(seconds=int(elapsed)))}")
            self.after(1000, self.update_timer)

# --- Completion Frame (WITH INTEGRATED CERTIFICATE VIEWER) ---
class CompletionFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.wiped_devices = []
        self.backend_client = None
        
        # Initialize backend client if available
        if HAS_BACKEND_INTEGRATION:
            self.initialize_backend_client()
        
        # Setup UI
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=2)  # For certificate viewer
        
        # Header
        header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=20, sticky="ew")
        
        self.success_label = customtkinter.CTkLabel(header_frame, text="✅ Wipe Operations Complete!", 
                                                   font=FONT_HEADER, text_color="green")
        self.success_label.pack()
        
        # Content area
        content_frame = customtkinter.CTkFrame(self)
        content_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        self.summary_label = customtkinter.CTkLabel(content_frame, text="", font=FONT_BODY_BOLD)
        self.summary_label.grid(row=0, column=0, pady=10, sticky="ew")
        
        self.cert_textbox = CustomTextbox(content_frame, state="disabled", font=FONT_MONO, 
                                         scrollbar_button_color="#FFD700")
        self.cert_textbox.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Action buttons
        footer_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=2, column=0, pady=20)
        
        self.generate_certs_button = customtkinter.CTkButton(footer_frame, text="Generate Certificates", 
                                                            font=FONT_BODY, fg_color="green", hover_color="darkgreen",
                                                            command=self.generate_certificates)
        self.generate_certs_button.pack(side="left", padx=10)
        
        self.return_button = customtkinter.CTkButton(footer_frame, text="Return to Dashboard", 
                                                    font=FONT_BODY, command=lambda: controller.show_frame(MainFrame))
        self.return_button.pack(side="right", padx=10)
        
        # --- INTEGRATED CERTIFICATE VIEWER ---
        if HAS_CERT_VIEWER:
            viewer_container = customtkinter.CTkFrame(self)
            viewer_container.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
            
            self.cert_viewer = CertificateViewerFrame(viewer_container, cert_dir=CERT_DIR)
            self.cert_viewer.pack(fill="both", expand=True)
        else:
            # Placeholder if viewer not available
            placeholder = customtkinter.CTkLabel(
                self, 
                text="Certificate viewer module not available",
                font=FONT_BODY,
                text_color="gray"
            )
            placeholder.grid(row=3, column=0, pady=10)
    
    def initialize_backend_client(self):
        """Initialize the backend client using credentials from login system"""
        try:
            print("\n" + "="*60)
            print("BACKEND AUTHENTICATION")
            print("="*60)
            
            # Read session data from login system
            session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obliterator_login", ".session_data")
            
            if not os.path.exists(session_file):
                print(f"⚠️ No session file found at: {session_file}")
                print("⚠️ Running in JSON-only mode (no PDFs)")
                self.backend_client = None
                print("="*60 + "\n")
                return
            
            # Load and decode session
            try:
                import base64
                with open(session_file, 'r') as f:
                    encrypted_data = f.read()
                
                decrypted_data = base64.b64decode(encrypted_data.encode()).decode()
                session_data = json.loads(decrypted_data)
                
                user_info = session_data.get('user', {})
                email = user_info.get('email')
                
                print(f"📧 Found authenticated user: {email}")
                
                # Check if we have table_auth (custom Users table auth)
                if user_info.get('table_auth'):
                    print("🔐 Using custom table authentication")
                    # For table auth, we create a simple token
                    auth_token = f"table_auth_{user_info.get('id')}"
                    
                    self.backend_client = CertificateBackendClient(
                        backend_url="https://obliterator-certificatebackend.onrender.com",
                        auth_token=auth_token,
                        supabase_auth=None
                    )
                else:
                    # Standard Supabase auth - need to re-authenticate to get fresh token
                    print("🔐 Re-authenticating with Supabase for fresh token...")
                    supabase_auth = SupabaseAuth(SUPABASE_URL, SUPABASE_KEY)
                    
                    # We don't have the password, but we have the email
                    # Try to use the stored access token if available
                    if 'access_token' in session_data:
                        supabase_auth.auth_token = session_data['access_token']
                        supabase_auth.user_info = user_info
                        print("✅ Using stored access token")
                    else:
                        print("⚠️ No stored token - backend may not work")
                        self.backend_client = None
                        print("="*60 + "\n")
                        return
                    
                    self.backend_client = CertificateBackendClient(
                        backend_url="https://obliterator-certificatebackend.onrender.com",
                        supabase_auth=supabase_auth
                    )
                
                # Test connection
                print(f"Testing backend connection...")
                if self.backend_client.test_connection():
                    print("✅ Backend connected - PDF generation available")
                else:
                    print("⚠️ Backend offline - JSON only mode")
                    self.backend_client = None
                    
            except Exception as e:
                print(f"⚠️ Error reading session: {e}")
                print("⚠️ Running in JSON-only mode (no PDFs)")
                self.backend_client = None
                
        except Exception as e:
            print(f"❌ Backend initialization error: {e}")
            import traceback
            traceback.print_exc()
            self.backend_client = None
        
        print("="*60 + "\n")
    
    def update_completion_info(self, wiped_devices):
        self.wiped_devices = wiped_devices
        
        summary_text = f"Successfully wiped {len(wiped_devices)} device(s)"
        self.summary_label.configure(text=summary_text)
        
        self.cert_textbox.configure(state="normal")
        self.cert_textbox.delete("1.0", "end")
        
        devices_text = "Successfully Wiped Devices:\n" + ("-" * 50) + "\n"
        for i, device in enumerate(wiped_devices, 1):
            devices_text += f"{i}. /dev/{device['name']} ({device['model']}, {device['size']})\n"
            devices_text += f"   Serial: {device['serial_number']}\n\n"
        
        devices_text += ("\nNext Steps:\n" + ("-" * 20) + "\n" +
                        "1. Click 'Generate Certificates' to create signed wipe certificates\n" +
                        "2. Certificates will be saved to the certificates/ directory\n")
        
        if self.backend_client:
            devices_text += "3. PDFs will be automatically generated (Backend connected)\n"
        else:
            devices_text += "3. PDFs unavailable (Backend offline - JSON only)\n"
        
        self.cert_textbox.insert("1.0", devices_text)
        self.cert_textbox.configure(state="disabled")
        
        # Refresh certificate viewer if available
        if HAS_CERT_VIEWER and hasattr(self, 'cert_viewer'):
            self.cert_viewer.refresh_certificate_list()
    
    def generate_certificates(self):
        """Generate certificates for all wiped devices"""
        self.generate_certs_button.configure(state="disabled", text="Generating...")
        
        self.cert_textbox.configure(state="normal")
        self.cert_textbox.insert("end", "\n" + ("=" * 50) + "\nGenerating Certificates...\n" + ("=" * 50) + "\n")
        self.cert_textbox.configure(state="disabled")
        
        threading.Thread(target=self.run_certificate_generation, daemon=True).start()
    
    def run_certificate_generation(self):
        """Run certificate generation for each device"""
        success_count = 0
        pdf_success_count = 0
        total_devices = len(self.wiped_devices)
        
        # Ensure certificate directory exists
        os.makedirs(CERT_DIR, exist_ok=True)
        
        for i, device in enumerate(self.wiped_devices, 1):
            device_path = f"/dev/{device['name']}"
            serial_number = device['serial_number']
            
            self.after(0, lambda d=device['name'], i=i, t=total_devices: self.update_cert_status(
                f"\n[{i}/{t}] Generating certificate for /dev/{d}..."))
            
            try:
                # Generate JSON certificate
                if not os.path.exists(CERT_GENERATOR_PATH):
                    self.after(0, lambda: self.update_cert_status(
                        f"❌ ERROR: Certificate generator not found at: {CERT_GENERATOR_PATH}"))
                    continue
                    
                if not os.access(CERT_GENERATOR_PATH, os.X_OK):
                    self.after(0, lambda: self.update_cert_status(
                        f"❌ ERROR: Certificate generator not executable: {CERT_GENERATOR_PATH}"))
                    continue
                
                # Log the exact command being run
                cmd = ['bash', CERT_GENERATOR_PATH, device_path, serial_number, 
                       'Success', APP_NAME, APP_VERSION]
                self.after(0, lambda c=cmd: self.update_cert_status(
                    f"DEBUG: Running command: {' '.join(c)}"))
                
                # Run with better error capture
                result = subprocess.run(
                    cmd,
                    capture_output=True, 
                    text=True, 
                    timeout=30,
                    cwd=SCRIPT_DIR  # Important: run in script directory
                )
                
                # Log all output for debugging
                if result.stdout:
                    self.after(0, lambda out=result.stdout: self.update_cert_status(
                        f"DEBUG: Script stdout:\n{out}"))
                
                if result.stderr:
                    self.after(0, lambda err=result.stderr: self.update_cert_status(
                        f"DEBUG: Script stderr:\n{err}"))
                
                if result.returncode != 0:
                    self.after(0, lambda rc=result.returncode, err=result.stderr: self.update_cert_status(
                        f"❌ Certificate generation failed (exit code {rc})\n{err[:200]}"))
                    continue
                
                # Try multiple methods to find the JSON file
                json_filepath = None
                
                # Method 1: Parse from stdout
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'File:' in line or 'Certificate saved to:' in line or '.json' in line:
                        # Extract filepath from various possible formats
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            potential_path = parts[1].strip()
                            if os.path.exists(potential_path):
                                json_filepath = potential_path
                                break
                
                # Method 2: Look for recently created files in cert directory
                if not json_filepath:
                    self.after(0, lambda: self.update_cert_status(
                        "DEBUG: Searching for recently created JSON files..."))
                    
                    # Wait a moment for file system to sync
                    time.sleep(0.5)
                    
                    # Find .json files modified in last 10 seconds
                    recent_files = []
                    try:
                        for filename in os.listdir(CERT_DIR):
                            if filename.endswith('.json'):
                                filepath = os.path.join(CERT_DIR, filename)
                                if os.path.getmtime(filepath) > (time.time() - 10):
                                    # Check if this file contains our serial number
                                    try:
                                        with open(filepath, 'r') as f:
                                            content = json.load(f)
                                            if content.get('serial_number') == serial_number:
                                                recent_files.append(filepath)
                                    except:
                                        pass
                        
                        if recent_files:
                            json_filepath = recent_files[0]  # Use most recent match
                            self.after(0, lambda p=json_filepath: self.update_cert_status(
                                f"DEBUG: Found JSON file: {p}"))
                    except Exception as e:
                        self.after(0, lambda e=str(e): self.update_cert_status(
                            f"DEBUG: Error searching for files: {e}"))
                
                # Method 3: Construct expected filename
                if not json_filepath:
                    self.after(0, lambda: self.update_cert_status(
                        "DEBUG: Using fallback filename construction..."))
                    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    json_filename = f"wipe-{timestamp}-{serial_number}.json"
                    json_filepath = os.path.join(CERT_DIR, json_filename)
                
                # Verify file exists and is valid
                if os.path.exists(json_filepath):
                    try:
                        with open(json_filepath, 'r') as f:
                            cert_data = json.load(f)
                        
                        success_count += 1
                        self.after(0, lambda d=device['name'], p=json_filepath: self.update_cert_status(
                            f"✅ JSON certificate generated for /dev/{d}\n   File: {p}"))
                        
                        # Try PDF generation if backend available
                        if self.backend_client:
                            self.after(0, lambda d=device['name']: self.update_cert_status(
                                f"📤 Sending /dev/{d} certificate to backend..."))
                            
                            success_pdf, pdf_url, error = self.backend_client.generate_pdf_from_json(json_filepath)
                            
                            if success_pdf and pdf_url:
                                pdf_success_count += 1
                                pdf_filename = os.path.basename(json_filepath).replace('.json', '.pdf')
                                pdf_path = os.path.join(CERT_DIR, pdf_filename)
                                
                                if self.backend_client.download_pdf(pdf_url, pdf_path):
                                    self.after(0, lambda d=device['name']: self.update_cert_status(
                                        f"✅ PDF downloaded for /dev/{d}"))
                                else:
                                    self.after(0, lambda d=device['name']: self.update_cert_status(
                                        f"⚠️ PDF generated but download failed for /dev/{d}"))
                            elif success_pdf:
                                pdf_success_count += 1
                                self.after(0, lambda d=device['name']: self.update_cert_status(
                                    f"✅ PDF generated for /dev/{d}"))
                            else:
                                self.after(0, lambda d=device['name'], e=error: self.update_cert_status(
                                    f"⚠️ PDF generation failed for /dev/{d}: {str(e)[:100]}"))
                                
                    except json.JSONDecodeError as e:
                        self.after(0, lambda d=device['name'], e=str(e): self.update_cert_status(
                            f"⚠️ JSON file created but invalid for /dev/{d}: {e}"))
                else:
                    self.after(0, lambda d=device['name'], p=json_filepath: self.update_cert_status(
                        f"❌ JSON file not found for /dev/{d}\n   Expected: {p}\n   Directory contents: {os.listdir(CERT_DIR) if os.path.exists(CERT_DIR) else 'DIR NOT FOUND'}"))
                        
            except subprocess.TimeoutExpired:
                self.after(0, lambda d=device['name']: self.update_cert_status(
                    f"❌ Certificate generation timed out for /dev/{d}"))
            except Exception as e:
                self.after(0, lambda d=device['name'], e=str(e): self.update_cert_status(
                    f"❌ Unexpected error for /dev/{d}: {e}"))
                import traceback
                self.after(0, lambda tb=traceback.format_exc(): self.update_cert_status(
                    f"DEBUG: Traceback:\n{tb}"))
        
        # Final status
        self.after(0, lambda: self.certificate_generation_complete(
            success_count, pdf_success_count, total_devices))
        
        # Refresh certificate viewer
        if HAS_CERT_VIEWER and hasattr(self, 'cert_viewer'):
            self.after(0, lambda: self.cert_viewer.refresh_certificate_list())
    
    def certificate_generation_complete(self, json_count, pdf_count, total_devices):
        """Handle completion of certificate generation"""
        self.generate_certs_button.configure(state="normal", text="Generate Certificates")
        
        completion_message = f"\n{'='*50}\nCertificate Generation Complete!\n{'='*50}\n"
        completion_message += f"JSON Certificates: {json_count}/{total_devices} generated\n"
        
        if pdf_count > 0:
            completion_message += f"PDF Certificates: {pdf_count}/{total_devices} generated\n"
        
        completion_message += f"Location: {CERT_DIR}\n\n"
        
        if json_count == total_devices:
            if pdf_count == total_devices:
                completion_message += "All certificates (JSON + PDF) generated successfully! ✅\n"
            elif pdf_count > 0:
                completion_message += f"All JSON certificates generated! {pdf_count} PDFs created.\n"
            else:
                completion_message += "All JSON certificates generated! (Backend unavailable for PDFs)\n"
        else:
            completion_message += f"⚠️ {total_devices - json_count} certificates failed to generate.\n"
            
        self.cert_textbox.configure(state="normal")
        self.cert_textbox.insert("end", completion_message)
        self.cert_textbox.see("end")
        self.cert_textbox.configure(state="disabled")
    
    def update_cert_status(self, message):
        """Update certificate generation status in UI"""
        self.cert_textbox.configure(state="normal")
        self.cert_textbox.insert("end", f"{message}\n")
        self.cert_textbox.see("end")
        self.cert_textbox.configure(state="disabled")

# --- Entry Point ---
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Error: This application requires root privileges.")
        print("Please run with 'sudo python3 obliterator_gui_integrated.py'")
        sys.exit(1)
    else:
        # Check authentication
        if not check_authentication():
            print("Authentication required. Exiting.")
            sys.exit(1)
        
        # Start main application
        print(f"\n{'='*60}")
        print(f"Starting {APP_NAME} v{APP_VERSION}")
        print(f"Backend Integration: {'✅ Available' if HAS_BACKEND_INTEGRATION else '❌ Unavailable'}")
        print(f"Certificate Viewer: {'✅ Available' if HAS_CERT_VIEWER else '❌ Unavailable'}")
        print(f"{'='*60}\n")
        
        app = App()
        app.mainloop()
