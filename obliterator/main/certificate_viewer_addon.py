#!/usr/bin/env python3
# certificate_viewer_addon.py
# Add-on module to integrate into the CompletionFrame class of the main GUI
# This adds view/download capabilities for JSON and PDF certificates
# Updated to handle flat JSON structure (no certificate_payload wrapper)

import tkinter as tk
import customtkinter
import json
import os
import subprocess
import threading
from tkinter import filedialog, messagebox
from datetime import datetime

# Import the backend integration module
try:
    from certificate_backend_integration import CertificateBackendClient
    HAS_BACKEND_INTEGRATION = True
except ImportError:
    HAS_BACKEND_INTEGRATION = False
    print("Warning: Backend integration module not found. PDF generation will be unavailable.")

class CertificateViewerFrame(customtkinter.CTkFrame):
    """Frame for viewing and managing certificates"""
    
    def __init__(self, parent, cert_dir="./certificates", **kwargs):
        super().__init__(parent, **kwargs)
        self.cert_dir = cert_dir
        self.backend_client = None
        
        # Initialize backend client if available
        if HAS_BACKEND_INTEGRATION:
            self.backend_client = CertificateBackendClient()
            self.test_backend_connection()
        
        self.setup_ui()
        self.refresh_certificate_list()
    
    def test_backend_connection(self):
        """Test connection to backend server"""
        if self.backend_client:
            if self.backend_client.test_connection():
                print("Backend server connected")
            else:
                print("Backend server not available - PDF generation disabled")
                self.backend_client = None
    
    def setup_ui(self):
        """Setup the certificate viewer UI"""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        title_label = customtkinter.CTkLabel(
            header_frame,
            text="Certificate Manager",
            font=("Roboto", 20, "bold")
        )
        title_label.grid(row=0, column=0, padx=10, sticky="w")
        
        # Refresh button
        refresh_btn = customtkinter.CTkButton(
            header_frame,
            text="Refresh",
            width=100,
            command=self.refresh_certificate_list
        )
        refresh_btn.grid(row=0, column=2, padx=5)
        
        # Main content area
        content_frame = customtkinter.CTkFrame(self)
        content_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=2)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Certificate list (left side)
        list_frame = customtkinter.CTkFrame(content_frame)
        list_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        list_frame.grid_rowconfigure(1, weight=1)
        
        list_label = customtkinter.CTkLabel(
            list_frame,
            text="Available Certificates",
            font=("Roboto", 14, "bold")
        )
        list_label.grid(row=0, column=0, padx=5, pady=5)
        
        # Scrollable list
        self.cert_listbox = customtkinter.CTkScrollableFrame(list_frame)
        self.cert_listbox.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Certificate viewer (right side)
        viewer_frame = customtkinter.CTkFrame(content_frame)
        viewer_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        viewer_frame.grid_rowconfigure(1, weight=1)
        
        viewer_label = customtkinter.CTkLabel(
            viewer_frame,
            text="Certificate Details",
            font=("Roboto", 14, "bold")
        )
        viewer_label.grid(row=0, column=0, padx=5, pady=5)
        
        # Text viewer
        self.cert_viewer = customtkinter.CTkTextbox(
            viewer_frame,
            font=("Courier", 11),
            state="disabled"
        )
        self.cert_viewer.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Action buttons
        action_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        # View JSON button
        self.view_json_btn = customtkinter.CTkButton(
            action_frame,
            text="View JSON",
            state="disabled",
            command=self.view_selected_json
        )
        self.view_json_btn.pack(side="left", padx=5)
        
        # Download JSON button
        self.download_json_btn = customtkinter.CTkButton(
            action_frame,
            text="Save JSON",
            state="disabled",
            command=self.save_selected_json
        )
        self.download_json_btn.pack(side="left", padx=5)
        
        # Generate PDF button
        self.generate_pdf_btn = customtkinter.CTkButton(
            action_frame,
            text="Generate PDF",
            state="disabled",
            fg_color="green",
            hover_color="darkgreen",
            command=self.generate_pdf_for_selected
        )
        self.generate_pdf_btn.pack(side="left", padx=5)
        
        if not HAS_BACKEND_INTEGRATION or not self.backend_client:
            self.generate_pdf_btn.configure(
                state="disabled",
                text="PDF (Backend Offline)"
            )
        
        # Batch PDF generation
        self.batch_pdf_btn = customtkinter.CTkButton(
            action_frame,
            text="Generate All PDFs",
            fg_color="orange",
            hover_color="darkorange",
            command=self.batch_generate_pdfs
        )
        self.batch_pdf_btn.pack(side="left", padx=5)
        
        if not HAS_BACKEND_INTEGRATION or not self.backend_client:
            self.batch_pdf_btn.configure(state="disabled")
        
        # Status label
        self.status_label = customtkinter.CTkLabel(
            action_frame,
            text="",
            font=("Roboto", 12)
        )
        self.status_label.pack(side="right", padx=10)
        
        self.selected_cert_file = None
    
    def refresh_certificate_list(self):
        """Refresh the list of available certificates"""
        # Clear existing list
        for widget in self.cert_listbox.winfo_children():
            widget.destroy()
        
        if not os.path.exists(self.cert_dir):
            label = customtkinter.CTkLabel(
                self.cert_listbox,
                text="No certificates directory found",
                text_color="gray"
            )
            label.pack(pady=10)
            return
        
        # Find all JSON certificates
        cert_files = [f for f in os.listdir(self.cert_dir) if f.endswith('.json')]
        
        if not cert_files:
            label = customtkinter.CTkLabel(
                self.cert_listbox,
                text="No certificates found",
                text_color="gray"
            )
            label.pack(pady=10)
            return
        
        # Create button for each certificate
        for cert_file in sorted(cert_files, reverse=True):
            # Extract info from filename
            parts = cert_file.replace('.json', '').split('-')
            timestamp = '-'.join(parts[1:3]) if len(parts) >= 3 else "Unknown"
            serial = '-'.join(parts[3:]) if len(parts) > 3 else "Unknown"
            
            btn = customtkinter.CTkButton(
                self.cert_listbox,
                text=f"{cert_file[:35]}...\n{timestamp}",
                anchor="w",
                command=lambda f=cert_file: self.select_certificate(f)
            )
            btn.pack(fill="x", padx=5, pady=2)
        
        self.status_label.configure(text=f"Found {len(cert_files)} certificate(s)")
    
    def select_certificate(self, cert_file):
        """Select and display a certificate"""
        self.selected_cert_file = cert_file
        cert_path = os.path.join(self.cert_dir, cert_file)
        
        try:
            with open(cert_path, 'r') as f:
                cert_data = json.load(f)
            
            # Display certificate info
            self.display_certificate(cert_data)
            
            # Enable action buttons
            self.view_json_btn.configure(state="normal")
            self.download_json_btn.configure(state="normal")
            
            if self.backend_client:
                self.generate_pdf_btn.configure(state="normal")
            
            self.status_label.configure(text=f"Selected: {cert_file}")
            
        except Exception as e:
            self.status_label.configure(text=f"Error loading certificate: {str(e)}")
    
    def display_certificate(self, cert_data):
        """Display certificate details in viewer - handles both flat and wrapped formats"""
        self.cert_viewer.configure(state="normal")
        self.cert_viewer.delete("1.0", "end")
        
        # Handle both old (wrapped) and new (flat) formats
        if 'certificate_payload' in cert_data:
            # Old format with wrapper
            payload = cert_data['certificate_payload']
            signature = cert_data.get('signature', {})
        else:
            # New flat format
            payload = cert_data
            signature = cert_data.get('signature', {})
        
        metadata = payload.get('certificate_metadata', {})
        media_info = payload.get('media_information', {})
        tool_info = payload.get('tool_information', {})
        event_info = payload.get('sanitization_event', {})
        details_info = payload.get('sanitization_details', {})
        
        # Format display
        display_text = "CERTIFICATE DETAILS\n" + "="*50 + "\n\n"
        
        display_text += "Certificate Information:\n"
        display_text += f"  ID: {metadata.get('certificate_id', 'N/A')}\n"
        display_text += f"  Generated: {metadata.get('generated_timestamp', 'N/A')}\n"
        display_text += f"  Version: {metadata.get('version', 'N/A')}\n"
        display_text += f"  Standard: {metadata.get('nist_reference', 'N/A')}\n\n"
        
        display_text += "Device Information:\n"
        display_text += f"  Path: {media_info.get('device_path', 'N/A')}\n"
        display_text += f"  Manufacturer: {media_info.get('manufacturer', 'N/A')}\n"
        display_text += f"  Model: {media_info.get('model', 'N/A')}\n"
        display_text += f"  Serial: {media_info.get('serial_number', 'N/A')}\n"
        display_text += f"  Type: {media_info.get('media_type', 'N/A')}\n"
        display_text += f"  Size: {media_info.get('capacity_gb', 0)} GB\n"
        display_text += f"  Interface: {media_info.get('interface_type', 'N/A')}\n\n"
        
        display_text += "Sanitization Information:\n"
        display_text += f"  Tool: {tool_info.get('name', 'N/A')} v{tool_info.get('version', 'N/A')}\n"
        display_text += f"  Method: {tool_info.get('method', 'N/A')}\n"
        display_text += f"  Technique: {tool_info.get('technique', 'N/A')}\n"
        display_text += f"  Status: {event_info.get('status', 'N/A')}\n"
        display_text += f"  Verification: {details_info.get('verification_status', 'N/A')}\n\n"
        
        if signature:
            display_text += "Digital Signature:\n"
            display_text += f"  Algorithm: {signature.get('algorithm', 'N/A')}\n"
            display_text += f"  Format: {signature.get('format', 'N/A')}\n"
            display_text += f"  Timestamp: {signature.get('signed_timestamp', 'N/A')}\n"
            sig_value = signature.get('value', '')
            if sig_value:
                display_text += f"  Signature: {sig_value[:60]}...\n"
        
        self.cert_viewer.insert("1.0", display_text)
        self.cert_viewer.configure(state="disabled")
    
    def view_selected_json(self):
        """View the full JSON of selected certificate"""
        if not self.selected_cert_file:
            return
        
        cert_path = os.path.join(self.cert_dir, self.selected_cert_file)
        
        # Open in system default JSON viewer/editor
        if os.name == 'nt':  # Windows
            os.startfile(cert_path)
        elif os.name == 'posix':  # Linux/Mac
            subprocess.call(['xdg-open', cert_path])
    
    def save_selected_json(self):
        """Save selected certificate to user-chosen location"""
        if not self.selected_cert_file:
            return
        
        src_path = os.path.join(self.cert_dir, self.selected_cert_file)
        
        # Ask user where to save
        dest_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=self.selected_cert_file
        )
        
        if dest_path:
            try:
                with open(src_path, 'r') as src, open(dest_path, 'w') as dst:
                    json.dump(json.load(src), dst, indent=2)
                self.status_label.configure(text=f"Saved to: {os.path.basename(dest_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save certificate: {str(e)}")
    
    def generate_pdf_for_selected(self):
        """Generate PDF for selected certificate"""
        if not self.selected_cert_file or not self.backend_client:
            return
        
        cert_path = os.path.join(self.cert_dir, self.selected_cert_file)
        
        self.generate_pdf_btn.configure(state="disabled", text="Generating...")
        self.status_label.configure(text="Generating PDF...")
        
        # Run in thread to avoid blocking UI
        threading.Thread(
            target=self._generate_pdf_thread,
            args=(cert_path,),
            daemon=True
        ).start()
    
    def _generate_pdf_thread(self, cert_path):
        """Thread function for PDF generation"""
        success, pdf_url, error = self.backend_client.generate_pdf_from_json(cert_path)
        
        if success:
            if pdf_url:
                # Download PDF locally
                pdf_filename = os.path.basename(cert_path).replace('.json', '.pdf')
                pdf_path = os.path.join(self.cert_dir, pdf_filename)
                
                if self.backend_client.download_pdf(pdf_url, pdf_path):
                    self.after(0, lambda: self.status_label.configure(
                        text=f"PDF saved: {pdf_filename}"
                    ))
                else:
                    self.after(0, lambda: self.status_label.configure(
                        text="PDF generated but download failed"
                    ))
            else:
                self.after(0, lambda: self.status_label.configure(
                    text="PDF generated successfully"
                ))
        else:
            self.after(0, lambda e=error: self.status_label.configure(
                text=f"PDF generation failed: {str(e)[:50]}"
            ))
        
        self.after(0, lambda: self.generate_pdf_btn.configure(
            state="normal", text="Generate PDF"
        ))
    
    def batch_generate_pdfs(self):
        """Generate PDFs for all certificates"""
        if not self.backend_client:
            return
        
        response = messagebox.askyesno(
            "Batch PDF Generation",
            "Generate PDFs for all certificates?\nThis may take several minutes."
        )
        
        if not response:
            return
        
        self.batch_pdf_btn.configure(state="disabled", text="Processing...")
        self.status_label.configure(text="Batch processing certificates...")
        
        # Run in thread
        threading.Thread(target=self._batch_pdf_thread, daemon=True).start()
    
    def _batch_pdf_thread(self):
        """Thread function for batch PDF generation"""
        results = self.backend_client.batch_process_certificates(
            self.cert_dir,
            self.cert_dir  # Save PDFs in same directory
        )
        
        # Update UI with results
        self.after(0, lambda: self.status_label.configure(
            text=f"Batch complete: {results['successful']}/{results['processed']} PDFs generated"
        ))
        
        self.after(0, lambda: self.batch_pdf_btn.configure(
            state="normal", text="Generate All PDFs"
        ))
        
        if results['failed'] > 0:
            failed_list = "\n".join([
                f"- {cert['json_file']}"
                for cert in results['certificates']
                if not cert['success']
            ])
            self.after(0, lambda: messagebox.showwarning(
                "Batch Processing Complete",
                f"Generated {results['successful']} PDFs.\n"
                f"{results['failed']} failed:\n{failed_list[:200]}"
            ))


# Integration function to add to existing CompletionFrame
def integrate_certificate_viewer(completion_frame, cert_dir):
    """
    Function to integrate certificate viewer into existing CompletionFrame
    Call this from your main GUI to add the certificate viewer
    """
    cert_viewer = CertificateViewerFrame(completion_frame, cert_dir=cert_dir)
    cert_viewer.pack(fill="both", expand=True, padx=10, pady=10)
    return cert_viewer
