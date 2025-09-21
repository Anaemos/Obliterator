#!/usr/bin/env python3
"""
SecureWipe Pro - Main Application Integration Example
Shows how to integrate the login system with your main data wiping application
"""

import customtkinter as ctk
from login_system import LoginSystem
import tkinter.messagebox as messagebox
import sys
import os

class SecureWipeMainApp(ctk.CTk):
    """Main application that uses the login system"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize login system
        self.login_system = LoginSystem()
        self.user_data = None
        
        # Configure main window
        self.title("SecureWipe Pro - Data Wiping Tool")
        self.geometry("800x600")
        self.configure(fg_color="#1a1a2e")
        
        # Hide window until authentication
        self.withdraw()
        
        # Authenticate user first
        self.authenticate_and_start()
    
    def authenticate_and_start(self):
        """Handle authentication and start main app"""
        try:
            print("🔐 Starting authentication...")
            
            # Run login system
            if self.login_system.authenticate_user():
                # Authentication successful
                self.user_data = self.login_system.get_user_session()
                print(f"✅ User authenticated: {self.user_data.get('email')}")
                
                # Show main window
                self.deiconify()
                self.center_window()
                
                # Setup main interface
                self.setup_main_interface()
                
            else:
                # Authentication failed
                print("❌ Authentication failed or cancelled")
                self.destroy()
                
        except Exception as e:
            print(f"💥 Authentication error: {e}")
            messagebox.showerror("Authentication Error", f"Failed to authenticate:\n{e}")
            self.destroy()
    
    def center_window(self):
        """Center main window"""
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"800x600+{x}+{y}")
    
    def setup_main_interface(self):
        """Setup the main application interface"""
        # Header frame
        header_frame = ctk.CTkFrame(self, fg_color="#16213e", height=80)
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        header_frame.pack_propagate(False)
        
        # Left side - app info
        info_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=20, pady=15)
        
        app_title = ctk.CTkLabel(
            info_frame,
            text="SecureWipe Pro",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#bb86fc"
        )
        app_title.pack(anchor="w")
        
        user_info = ctk.CTkLabel(
            info_frame,
            text=f"Authenticated as: {self.user_data.get('email')}",
            font=ctk.CTkFont(size=11),
            text_color="#8692f7"
        )
        user_info.pack(anchor="w")
        
        # Right side - controls
        controls_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        controls_frame.pack(side="right", padx=20, pady=15)
        
        logout_btn = ctk.CTkButton(
            controls_frame,
            text="Logout",
            width=80,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self.handle_logout
        )
        logout_btn.pack()
        
        # Main content area
        content_frame = ctk.CTkFrame(self, fg_color="#16213e")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Welcome message
        welcome_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        welcome_frame.pack(fill="both", expand=True, padx=30, pady=30)
        
        welcome_title = ctk.CTkLabel(
            welcome_frame,
            text="Welcome to SecureWipe Pro!",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#bb86fc"
        )
        welcome_title.pack(pady=(0, 10))
        
        welcome_text = ctk.CTkLabel(
            welcome_frame,
            text="Professional Data Wiping Solution\nSecure • Reliable • Compliant",
            font=ctk.CTkFont(size=14),
            text_color="#8692f7"
        )
        welcome_text.pack(pady=(0, 30))
        
        # Mock data wiping interface
        self.setup_wiping_interface(welcome_frame)
    
    def setup_wiping_interface(self, parent):
        """Setup mock data wiping interface"""
        # Drive selection section
        drive_frame = ctk.CTkFrame(parent, fg_color="#0f1419")
        drive_frame.pack(fill="x", pady=(0, 20))
        
        drive_title = ctk.CTkLabel(
            drive_frame,
            text="🗂️ Drive Selection",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        drive_title.pack(pady=(15, 10), padx=20, anchor="w")
        
        drive_info = ctk.CTkLabel(
            drive_frame,
            text="No drives detected. Connect a drive to begin wiping process.",
            font=ctk.CTkFont(size=12),
            text_color="#8692f7"
        )
        drive_info.pack(pady=(0, 15), padx=20, anchor="w")
        
        # Wipe method selection
        method_frame = ctk.CTkFrame(parent, fg_color="#0f1419")
        method_frame.pack(fill="x", pady=(0, 20))
        
        method_title = ctk.CTkLabel(
            method_frame,
            text="🔧 Wipe Method",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        method_title.pack(pady=(15, 10), padx=20, anchor="w")
        
        self.wipe_method_var = ctk.StringVar(value="Quick Wipe")
        method_menu = ctk.CTkOptionMenu(
            method_frame,
            values=["Quick Wipe (1 Pass)", "Secure Wipe (3 Pass)", "Military Grade (7 Pass)"],
            variable=self.wipe_method_var,
            font=ctk.CTkFont(size=12),
            fg_color="#bb86fc",
            button_color="#9c6dfd",
            dropdown_fg_color="#2d2d44"
        )
        method_menu.pack(pady=(0, 15), padx=20, anchor="w")
        
        # Action buttons
        action_frame = ctk.CTkFrame(parent, fg_color="#0f1419")
        action_frame.pack(fill="x")
        
        action_title = ctk.CTkLabel(
            action_frame,
            text="🚀 Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        action_title.pack(pady=(15, 10), padx=20, anchor="w")
        
        button_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_container.pack(pady=(0, 15), padx=20, anchor="w")
        
        scan_btn = ctk.CTkButton(
            button_container,
            text="Scan for Drives",
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#28a745",
            hover_color="#218838",
            command=self.scan_drives
        )
        scan_btn.pack(side="left", padx=(0, 10))
        
        wipe_btn = ctk.CTkButton(
            button_container,
            text="Start Wipe",
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self.start_wipe
        )
        wipe_btn.pack(side="left", padx=10)
        
        verify_btn = ctk.CTkButton(
            button_container,
            text="Verify Wipe",
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#6f42c1",
            hover_color="#5a359c",
            command=self.verify_wipe
        )
        verify_btn.pack(side="left", padx=(10, 0))
    
    def scan_drives(self):
        """Mock drive scanning function"""
        messagebox.showinfo(
            "Drive Scan", 
            "Drive scanning functionality would be implemented here.\n\nThis would detect and list all connected storage devices for wiping."
        )
    
    def start_wipe(self):
        """Mock wipe start function"""
        method = self.wipe_method_var.get()
        result = messagebox.askyesno(
            "Confirm Wipe",
            f"Are you sure you want to start {method}?\n\nThis action cannot be undone and will permanently destroy all data.",
            icon="warning"
        )
        
        if result:
            messagebox.showinfo(
                "Wipe Started",
                f"Data wiping process started with {method}.\n\nThis is where the actual wiping logic would be implemented."
            )
    
    def verify_wipe(self):
        """Mock wipe verification function"""
        messagebox.showinfo(
            "Verify Wipe",
            "Wipe verification functionality would be implemented here.\n\nThis would scan the drive to ensure data has been properly destroyed."
        )
    
    def handle_logout(self):
        """Handle user logout"""
        result = messagebox.askyesno(
            "Logout Confirmation",
            "Are you sure you want to logout?\n\nAny active operations will be stopped.",
            icon="warning"
        )
        
        if result:
            print("🔓 User logging out...")
            
            # Logout from login system
            self.login_system.logout()
            
            # Close current window
            self.destroy()
            
            # Restart authentication
            print("🔄 Restarting authentication...")
            new_app = SecureWipeMainApp()
            new_app.mainloop()

def main():
    """Main function"""
    print("🚀 Starting SecureWipe Pro with Authentication...")
    print("=" * 50)
    
    try:
        # Check if login system files exist
        required_files = ["login_system.py", "config.json"]
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        if missing_files:
            print(f"❌ Missing required files: {', '.join(missing_files)}")
            print("Please ensure all required files are in the same directory.")
            return
        
        # Create and run main application
        app = SecureWipeMainApp()
        app.mainloop()
        
        print("👋 Application closed.")
        
    except KeyboardInterrupt:
        print("\n⚠️  Application interrupted by user")
    except Exception as e:
        print(f"💥 Application error: {e}")
        messagebox.showerror("Application Error", f"An error occurred:\n{e}")

if __name__ == "__main__":
    main()