#!/usr/bin/env python3
"""
SecureWipe Pro - Complete Fixed Login System
Fullscreen, darker theme, better spacing, internet connectivity check
Modified to exit immediately after successful authentication
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import time
import os
import json
import base64
import sys
from datetime import datetime, timedelta
import requests
from typing import Optional, Dict, Any, Callable
import logging

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set CustomTkinter appearance - Darker theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Custom darker color palette
COLORS = {
    "primary_bg": "#0a0a0f",        # Very dark background
    "secondary_bg": "#12121a",      # Slightly lighter dark
    "card_bg": "#1a1a25",           # Card background
    "accent": "#7c3aed",            # Purple accent (darker)
    "accent_hover": "#6d28d9",      # Purple hover (darker)
    "text_primary": "#f8fafc",      # Light text
    "text_secondary": "#64748b",    # Secondary text
    "text_accent": "#a855f7",       # Purple text
    "success": "#22c55e",           # Success green
    "error": "#ef4444",             # Error red
    "input_bg": "#1e293b",          # Input background
    "border": "#475569"             # Border color
}

class ConfigManager:
    """Handles configuration loading"""
    
    def __init__(self):
        self.config_file = "config.json"
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or environment"""
        # Try environment variables first
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        # Try config file if env vars not found
        if not self.supabase_url or not self.supabase_key:
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.supabase_url = self.supabase_url or config.get("supabase_url")
                    self.supabase_key = self.supabase_key or config.get("supabase_key")
                    self.app_config = config.get("app_config", {})
                    self.security = config.get("security", {})
                    self.ui = config.get("ui", {})
            except FileNotFoundError:
                logger.error("No config.json found and no environment variables set")
                raise ValueError("Configuration not found")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase URL and key must be provided")

class SessionManager:
    """Handles user session management"""
    
    def __init__(self):
        self.session_file = ".session_data"
        self.session_data = {}
        self.load_session()
    
    def save_session(self, user_data: Dict[str, Any], remember_me: bool = False):
        """Save user session"""
        session_info = {
            "user": user_data,
            "timestamp": datetime.now().isoformat(),
            "remember_me": remember_me,
            "expires": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        # Simple encoding (in production, use proper encryption)
        encrypted_data = base64.b64encode(json.dumps(session_info).encode()).decode()
        
        try:
            with open(self.session_file, 'w') as f:
                f.write(encrypted_data)
            self.session_data = session_info
            logger.info("Session saved successfully")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def load_session(self) -> Optional[Dict[str, Any]]:
        """Load session data"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    encrypted_data = f.read()
                
                decrypted_data = base64.b64decode(encrypted_data.encode()).decode()
                self.session_data = json.loads(decrypted_data)
                
                # Check expiration
                expires = datetime.fromisoformat(self.session_data.get("expires", "1970-01-01"))
                if datetime.now() > expires:
                    self.clear_session()
                    return None
                
                return self.session_data
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            self.clear_session()
        
        return None
    
    def clear_session(self):
        """Clear session data"""
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            self.session_data = {}
            logger.info("Session cleared")
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def is_valid_session(self) -> bool:
        """Check if session is valid"""
        if not self.session_data:
            return False
        
        try:
            expires = datetime.fromisoformat(self.session_data.get("expires", "1970-01-01"))
            return datetime.now() < expires
        except:
            return False

class NetworkChecker:
    """Handles network connectivity checks"""
    
    @staticmethod
    def check_internet_connection() -> bool:
        """Check if internet connection is available"""
        try:
            # Try multiple reliable endpoints
            endpoints = [
                "https://www.google.com",
                "https://httpbin.org/get",
                "https://www.cloudflare.com"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code == 200:
                        return True
                except:
                    continue
            
            return False
        except Exception:
            return False
    
    @staticmethod
    def check_supabase_connection(url: str, headers: dict) -> bool:
        """Check Supabase specific connection"""
        try:
            import socket
            # DNS resolution check
            hostname = url.replace('https://', '').replace('http://', '')
            socket.gethostbyname(hostname.split('/')[0])
            
            # HTTP connection check
            response = requests.get(f"{url}/rest/v1/", headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

class AuthManager:
    """Handles Supabase authentication with custom User table"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.base_url = config.supabase_url
        self.headers = {
            "apikey": config.supabase_key,
            "Authorization": f"Bearer {config.supabase_key}",
            "Content-Type": "application/json"
        }
        self.current_user = None
        self.access_token = None
    
    def test_connection(self) -> bool:
        """Test Supabase connection"""
        return NetworkChecker.check_supabase_connection(self.base_url, self.headers)
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user using custom User table"""
        # Check internet connection first
        if not NetworkChecker.check_internet_connection():
            return {"success": False, "error": "No internet connection available"}
        
        try:
            # Method 1: Try Supabase Auth first (if you're using auth.users)
            auth_result = self._try_supabase_auth(email, password)
            if auth_result["success"]:
                return auth_result
            
            # Method 2: Try custom User table lookup
            table_result = self._try_user_table_auth(email, password)
            if table_result["success"]:
                return table_result
            
            # Both methods failed
            return {"success": False, "error": "Invalid email or password"}
                
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            return {"success": False, "error": f"Connection error: {str(e)}"}
    
    def _try_supabase_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Try standard Supabase auth"""
        try:
            url = f"{self.base_url}/auth/v1/token?grant_type=password"
            data = {"email": email, "password": password}
            
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            result = response.json()
            
            if response.status_code == 200:
                self.access_token = result.get("access_token")
                self.current_user = result.get("user")
                logger.info(f"User signed in via Supabase Auth: {email}")
                return {"success": True, "data": result, "method": "supabase_auth"}
            else:
                logger.info(f"Supabase Auth failed for {email}, trying User table")
                return {"success": False, "error": result.get("error_description", "Auth failed")}
                
        except Exception as e:
            logger.info(f"Supabase Auth error for {email}: {e}")
            return {"success": False, "error": str(e)}
    
    def _try_user_table_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Try authentication using custom Users table"""
        try:
            table_name = "Users"
            url = f"{self.base_url}/rest/v1/{table_name}"
            
            # Query for user by email
            params = {"email": f"eq.{email}", "select": "*"}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            logger.info(f"Searching for email: '{email}'")
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                users = response.json()
                logger.info(f"Found {len(users)} matching users")
                
                if not users:
                    return {"success": False, "error": "User not found"}
                
                user = users[0]
                
                # Check password
                stored_password = user.get("password")
                
                if self._verify_password(password, stored_password):
                    user_data = {
                        "id": str(user.get("id")),
                        "email": user.get("email"),
                        "user_metadata": {
                            "table_name": table_name
                        },
                        "created_at": user.get("created_at"),
                        "table_auth": True
                    }
                    
                    self.current_user = user_data
                    self.access_token = f"table_auth_{user.get('id')}"
                    
                    logger.info(f"Authentication successful for: {email}")
                    return {
                        "success": True, 
                        "data": {"user": user_data}, 
                        "method": "user_table"
                    }
                else:
                    logger.warning(f"Password mismatch for user: {email}")
                    return {"success": False, "error": "Invalid password"}
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text}")
                return {"success": False, "error": f"Database query failed: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"User table auth error: {e}")
            return {"success": False, "error": str(e)}
    
    def _verify_password(self, provided_password: str, stored_password: str) -> bool:
        """Verify password"""
        if not stored_password:
            return False
        
        # Simple plain text comparison
        return provided_password == stored_password
    
    def sign_out(self):
        """Sign out user"""
        self.current_user = None
        self.access_token = None
        logger.info("User signed out")

class FullscreenSplashScreen(ctk.CTk):
    """Simple, working fullscreen splash screen"""
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("Obliterator")
        self.configure(fg_color=COLORS["primary_bg"])
        
        # Simple fullscreen - get screen dimensions first
        self.update_idletasks()
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        
        # Set geometry to full screen
        self.geometry(f"{width}x{height}+0+0")
        self.attributes('-fullscreen', True)
        
        self.setup_ui()
        
        # Auto-close after 4 seconds
        self.after(4000, self.close_splash)
        
        # ESC to close early
        self.bind('<Escape>', lambda e: self.close_splash())
        self.focus_set()
    
    def setup_ui(self):
        """Setup splash UI"""
        # Main container
        main_frame = ctk.CTkFrame(
            self, 
            fg_color=COLORS["secondary_bg"], 
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True)
        
        # Center everything
        center_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        center_frame.pack(expand=True)
        
        # Load logo
        self.load_logo(center_frame)
        
        # "Wipe Beyond Recovery..." message
        message_label = ctk.CTkLabel(
            center_frame,
            text="Wipe Beyond Recovery...",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#ffffff"
        )
        message_label.pack(pady=(40, 60))
        
        # Loading text
        loading_label = ctk.CTkLabel(
            center_frame,
            text="Initializing secure authentication...",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_primary"]
        )
        loading_label.pack(pady=(0, 30))
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(
            center_frame,
            width=500,
            height=6,
            progress_color=COLORS["accent"],
            fg_color=COLORS["input_bg"]
        )
        progress_bar.pack(pady=(0, 60))
        progress_bar.set(0.8)
        
        # Version at bottom
        version_label = ctk.CTkLabel(
            main_frame,
            text="v1.0.0 | Obliterator Authentication System\nPress ESC to continue",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_secondary"]
        )
        version_label.pack(side="bottom", pady=40)
    
    def load_logo(self, parent):
        """Load logo image"""
        try:
            from PIL import Image
            
            if os.path.exists("Logo.png"):
                # Load and resize image
                pil_image = Image.open("Logo.png")
                original_width, original_height = pil_image.size
                
                # Resize to max 400px
                max_size = 400
                if original_width > original_height:
                    new_width = min(max_size, original_width)
                    new_height = int((new_width / original_width) * original_height)
                else:
                    new_height = min(max_size, original_height)
                    new_width = int((new_height / original_height) * original_width)
                
                resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create CTk image
                logo_image = ctk.CTkImage(
                    light_image=resized_image,
                    dark_image=resized_image,
                    size=(new_width, new_height)
                )
                
                # Display logo
                logo_label = ctk.CTkLabel(parent, image=logo_image, text="")
                logo_label.pack(pady=(100, 0))
                
                print(f"Logo loaded: {new_width}x{new_height}")
            else:
                self.show_text_logo(parent)
                
        except Exception as e:
            print(f"Logo error: {e}")
            self.show_text_logo(parent)
    
    def show_text_logo(self, parent):
        """Text fallback with updated branding"""
        title_label = ctk.CTkLabel(
            parent,
            text="Obliterator",
            font=ctk.CTkFont(size=72, weight="bold"),
            text_color=COLORS["accent"]
        )
        title_label.pack(pady=(100, 0))
    
    def close_splash(self):
        """Close splash"""
        self.destroy()

class FullscreenLoginWindow(ctk.CTk):
    """Simple fullscreen login window"""
    
    def __init__(self, auth_manager: AuthManager, session_manager: SessionManager):
        super().__init__()
        
        self.auth_manager = auth_manager
        self.session_manager = session_manager
        self.login_success_callback = None
        
        # Configure window
        self.title("Obliterator - Authentication")
        self.configure(fg_color=COLORS["primary_bg"])
        
        # Simple fullscreen
        self.update_idletasks()
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry(f"{width}x{height}+0+0")
        self.attributes('-fullscreen', True)
        
        self.setup_ui()
        self.check_existing_session()
        
        # ESC to exit (development)
        self.bind('<Escape>', lambda e: self.quit())
        self.focus_set()
    
    def setup_ui(self):
        """Setup login UI"""
        # Main background
        main_frame = ctk.CTkFrame(
            self, 
            fg_color=COLORS["secondary_bg"], 
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True)
        
        # Center container
        center_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        center_container.pack(expand=True)
        
        # Login card with bigger height to accommodate logo
        self.login_card = ctk.CTkFrame(
            center_container, 
            fg_color=COLORS["card_bg"], 
            corner_radius=20,
            width=600,
            height=650
        )
        self.login_card.pack()
        self.login_card.pack_propagate(False)
        
        self.setup_header()
        self.setup_login_form()
        self.setup_buttons()
        self.setup_footer()
    
    def setup_header(self):
        """Setup header with optimized spacing"""
        header_frame = ctk.CTkFrame(self.login_card, fg_color="transparent")
        header_frame.pack(fill="x", pady=(30, 20))
        
        # Load logo for header (optimized size)
        self.load_header_logo(header_frame)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Secure Authentication Required",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_secondary"]
        )
        subtitle_label.pack()
    
    def load_header_logo(self, parent):
        """Load logo for login header - using Logo2.png (pre-resized)"""
        try:
            from PIL import Image
            
            if os.path.exists("Logo2.png"):
                # Load Logo2.png
                pil_image = Image.open("Logo2.png")
                original_width, original_height = pil_image.size
                
                max_size = 250
                if original_width > max_size or original_height > max_size:
                    if original_width > original_height:
                        new_width = min(max_size, original_width)
                        new_height = int((new_width / original_width) * original_height)
                    else:
                        new_height = min(max_size, original_height)
                        new_width = int((new_height / original_height) * original_width)
                    
                    resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                else:
                    resized_image = pil_image
                    new_width, new_height = original_width, original_height
                
                # Create CTk image
                logo_image = ctk.CTkImage(
                    light_image=resized_image,
                    dark_image=resized_image,
                    size=(new_width, new_height)
                )
                
                # Display Logo2.png, centered
                logo_label = ctk.CTkLabel(parent, image=logo_image, text="")
                logo_label.pack(pady=(0, 10))
                
                print(f"Logo2.png loaded: {new_width}x{new_height}")
                
            elif os.path.exists("Logo.png"):
                # Fallback to original Logo.png if Logo2.png not found
                pil_image = Image.open("Logo.png")
                original_width, original_height = pil_image.size
                
                max_size = 150
                if original_width > original_height:
                    new_width = min(max_size, original_width)
                    new_height = int((new_width / original_width) * original_height)
                else:
                    new_height = min(max_size, original_height)
                    new_width = int((new_height / original_height) * original_width)
                
                resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                logo_image = ctk.CTkImage(
                    light_image=resized_image,
                    dark_image=resized_image,
                    size=(new_width, new_height)
                )
                
                logo_label = ctk.CTkLabel(parent, image=logo_image, text="")
                logo_label.pack(pady=(0, 10))
                
                print(f"Logo.png (fallback) loaded: {new_width}x{new_height}")
                
            else:
                # Text only fallback if neither logo found
                title_label = ctk.CTkLabel(
                    parent,
                    text="Obliterator",
                    font=ctk.CTkFont(size=32, weight="bold"),
                    text_color=COLORS["accent"]
                )
                title_label.pack(pady=(0, 10))
                print("No logo files found, using text fallback")
                
        except Exception as e:
            # Text only fallback on error
            title_label = ctk.CTkLabel(
                parent,
                text="Obliterator",
                font=ctk.CTkFont(size=32, weight="bold"),
                text_color=COLORS["accent"]
            )
            title_label.pack(pady=(0, 10))
            print(f"Logo error: {e}, using text fallback")
    
    def setup_login_form(self):
        """Setup login form with better spacing"""
        form_frame = ctk.CTkFrame(self.login_card, fg_color="transparent")
        form_frame.pack(fill="x", padx=60, pady=(0, 30))
        
        # Email with tighter spacing
        email_label = ctk.CTkLabel(
            form_frame,
            text="Email Address",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        email_label.pack(fill="x", pady=(0, 5))
        
        self.email_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Enter your email address",
            height=45,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.email_entry.pack(fill="x", pady=(0, 20))
        
        # Password with tighter spacing
        password_label = ctk.CTkLabel(
            form_frame,
            text="Password",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        password_label.pack(fill="x", pady=(0, 5))
        
        self.password_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Enter your password",
            show="*",
            height=45,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.password_entry.pack(fill="x", pady=(0, 20))
        
        # Remember me with tighter spacing
        self.remember_var = ctk.BooleanVar()
        self.remember_checkbox = ctk.CTkCheckBox(
            form_frame,
            text="Remember me for 24 hours",
            variable=self.remember_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        )
        self.remember_checkbox.pack(anchor="w", pady=(0, 20))
        
        # Status with less spacing
        self.status_label = ctk.CTkLabel(
            form_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["error"]
        )
        self.status_label.pack(fill="x", pady=(0, 10))
    
    def setup_buttons(self):
        """Setup buttons with optimized spacing"""
        button_frame = ctk.CTkFrame(self.login_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=60, pady=(0, 20))
        
        # Login button - slightly smaller
        self.login_button = ctk.CTkButton(
            button_frame,
            text="Sign In",
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["text_primary"],
            command=self.handle_login
        )
        self.login_button.pack(fill="x", pady=(0, 15))
        
        # Connection status
        self.connection_info = ctk.CTkLabel(
            button_frame,
            text="Checking network...",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        self.connection_info.pack()
        
        # Check network
        self.after(100, self.check_network_status)
        
        # Enter key binding
        self.bind('<Return>', lambda e: self.handle_login())
        self.email_entry.bind('<Return>', lambda e: self.handle_login())
        self.password_entry.bind('<Return>', lambda e: self.handle_login())
    
    def setup_footer(self):
        """Setup footer with reduced spacing"""
        footer_frame = ctk.CTkFrame(self.login_card, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", pady=20)
        
        security_label = ctk.CTkLabel(
            footer_frame,
            text="Secured with industry-standard encryption",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"]
        )
        security_label.pack()
    
    def check_network_status(self):
        """Check network connectivity"""
        def check():
            internet_ok = NetworkChecker.check_internet_connection()
            supabase_ok = self.auth_manager.test_connection() if internet_ok else False
            
            if internet_ok and supabase_ok:
                self.after(0, lambda: self.connection_info.configure(
                    text="Connected - Ready to authenticate",
                    text_color=COLORS["success"]
                ))
            elif internet_ok:
                self.after(0, lambda: self.connection_info.configure(
                    text="Internet OK - Auth server issues",
                    text_color="#f59e0b"
                ))
            else:
                self.after(0, lambda: self.connection_info.configure(
                    text="No internet connection",
                    text_color=COLORS["error"]
                ))
        
        threading.Thread(target=check, daemon=True).start()
    
    def check_existing_session(self):
        """Check for existing session"""
        session_data = self.session_manager.load_session()
        if session_data and self.session_manager.is_valid_session():
            if session_data.get("remember_me", False):
                self.auth_manager.current_user = session_data["user"]
                self.on_login_success(session_data["user"])
    
    def handle_login(self):
        """Handle login - simplified"""
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        
        if not email or not password:
            self.show_status("Please enter both email and password", error=True)
            return
        
        if "@" not in email:
            self.show_status("Please enter a valid email address", error=True)
            return
        
        # Check internet
        if not NetworkChecker.check_internet_connection():
            self.show_status("No internet connection. Check your network.", error=True)
            return
        
        self.login_button.configure(text="Signing In...", state="disabled")
        self.show_status("Authenticating...", error=False)
        
        threading.Thread(target=self._perform_login, args=(email, password), daemon=True).start()
    
    def _perform_login(self, email: str, password: str):
        """Perform login"""
        result = self.auth_manager.sign_in(email, password)
        self.after(0, self._handle_login_result, result)
    
    def _handle_login_result(self, result: Dict[str, Any]):
        """Handle login result"""
        self.login_button.configure(text="Sign In", state="normal")
        
        if result["success"]:
            user_data = result["data"]["user"]
            self.session_manager.save_session(user_data, self.remember_var.get())
            self.show_status("Login successful!", error=False)
            self.after(500, lambda: self.on_login_success(user_data))  # Brief delay then close
        else:
            self.show_status(f"{result['error']}", error=True)
    
    def show_status(self, message: str, error: bool = False):
        """Show status message"""
        color = COLORS["error"] if error else COLORS["success"]
        self.status_label.configure(text=message, text_color=color)
        
        if message and not message.startswith("Auth"):
            self.after(6000, lambda: self.status_label.configure(text=""))
    
    def set_login_success_callback(self, callback: Callable):
        """Set callback"""
        self.login_success_callback = callback
    
    def on_login_success(self, user_data: Dict[str, Any]):
        """Handle successful login - MODIFIED: Exit immediately, no success window"""
        if self.login_success_callback:
            self.login_success_callback(user_data)
        
        # Close the window immediately - no success message dialog
        self.destroy()

class LoginSystem:
    """Main login system coordinator"""
    
    def __init__(self):
        self.config = None
        self.auth_manager = None
        self.session_manager = None
        self.login_window = None
        self.user_data = None
        self.authenticated = False
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize system components"""
        try:
            self.config = ConfigManager()
            self.auth_manager = AuthManager(self.config)
            self.session_manager = SessionManager()
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            messagebox.showerror("Initialization Error", f"Failed to initialize login system:\n{e}")
            raise
    
    def authenticate_user(self) -> bool:
        """Simple, working authentication method"""
        try:
            print("Starting authentication...")
            
            # Show splash screen
            splash = FullscreenSplashScreen()
            splash.mainloop()
            
            # Small delay for cleanup
            time.sleep(0.2)
            
            # Show login window
            self.login_window = FullscreenLoginWindow(self.auth_manager, self.session_manager)
            self.login_window.set_login_success_callback(self._on_login_success)
            self.login_window.mainloop()
            
            return self.authenticated
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            messagebox.showerror("Authentication Error", f"Error: {e}")
            return False
    
    def _on_login_success(self, user_data: Dict[str, Any]):
        """Handle successful login - MODIFIED: Set data and close immediately"""
        self.user_data = user_data
        self.authenticated = True
        
        if self.login_window:
            self.login_window.quit()
    
    def get_user_session(self) -> Optional[Dict[str, Any]]:
        """Get user session data"""
        return self.user_data
    
    def get_user_email(self) -> Optional[str]:
        """Get user email"""
        return self.user_data.get("email") if self.user_data else None
    
    def get_user_id(self) -> Optional[str]:
        """Get user ID"""
        return self.user_data.get("id") if self.user_data else None
    
    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        return self.authenticated and self.user_data is not None
    
    def logout(self):
        """Logout user"""
        self.auth_manager.sign_out()
        self.session_manager.clear_session()
        self.user_data = None
        self.authenticated = False
        logger.info("User logged out")
    
    def get_access_token(self) -> Optional[str]:
        """Get access token"""
        return self.auth_manager.access_token

# MODIFIED: Main function - Exit immediately after authentication, no success window
def main():
    """Main function - MODIFIED: Exit immediately after successful authentication"""
    try:
        print("Starting Obliterator Authentication System...")
        print("=" * 60)
        print("Features:")
        print("- Fullscreen splash and login screens")
        print("- Internet connectivity checking")
        print("- Immediate exit after successful authentication")
        print("=" * 60)
        
        login_system = LoginSystem()
        
        if login_system.authenticate_user():
            user_data = login_system.get_user_session()
            print(f"Authentication successful!")
            print(f"User: {user_data.get('email')}")
            print(f"User ID: {user_data.get('id')}")
            
            # EXIT IMMEDIATELY WITH SUCCESS CODE - NO SUCCESS WINDOW
            sys.exit(0)
            
        else:
            print("Authentication failed or cancelled")
            # EXIT WITH FAILURE CODE
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()