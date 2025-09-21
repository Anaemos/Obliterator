from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import os
from datetime import datetime
import base64
import io
import json
import requests
import traceback
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Media Sanitization Certificate Generator", 
    version="2.0.0",
    description="Generate PDF certificates from sanitization data with user authentication"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"🔑 Supabase URL: {SUPABASE_URL}")
print(f"🔑 Supabase Key: {'Set' if SUPABASE_KEY else 'Not Set'}")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

# Simple Supabase client
class SimpleSupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    
    def verify_user(self, token: str):
        """Verify user token and get user info"""
        headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f"{self.url}/auth/v1/user", headers=headers)
        print(f"🔐 User verification response: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        return None
    
    def upload_file(self, bucket: str, filename: str, file_data: bytes):
        """Upload file to Supabase storage"""
        upload_url = f"{self.url}/storage/v1/object/{bucket}/{filename}"
        headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/pdf'
        }
        
        print(f"📤 Uploading to: {upload_url}")
        response = requests.post(upload_url, data=file_data, headers=headers)
        print(f"📤 Upload response: {response.status_code} - {response.text}")
        return response
    
    def get_public_url(self, bucket: str, filename: str):
        """Get public URL for uploaded file"""
        return f"{self.url}/storage/v1/object/public/{bucket}/{filename}"
    
    def insert_record(self, table: str, data: dict):
        """Insert record into database table"""
        insert_url = f"{self.url}/rest/v1/{table}"
        
        print(f"💾 Inserting to: {insert_url}")
        response = requests.post(insert_url, json=data, headers=self.headers)
        print(f"💾 Insert response: {response.status_code} - {response.text}")
        return response
    
    def select_records(self, table: str, filters: dict = None, limit: int = None, offset: int = None):
        """Select records from database table"""
        select_url = f"{self.url}/rest/v1/{table}"
        
        params = {}
        
        if filters:
            for key, value in filters.items():
                params[f"{key}"] = f"eq.{value}"
        
        if limit:
            params['limit'] = limit
        
        if offset:
            params['offset'] = offset
        
        response = requests.get(select_url, params=params, headers=self.headers)
        return response

# Initialize Supabase client
supabase = SimpleSupabaseClient(SUPABASE_URL, SUPABASE_KEY)

# Pydantic models
class SanitizationDetails(BaseModel):
    manufacturer: str = Field(..., description="Device manufacturer")
    model: str = Field(..., description="Device model")
    serial_number: str = Field(..., description="Device serial number")
    property_number: Optional[str] = Field(None, description="Organizational property number")
    media_type: str = Field(..., description="Type of media (magnetic, flash memory, hybrid)")
    media_source: str = Field(..., description="Source of media (user, computer)")
    pre_sanitization_confidentiality: Optional[str] = Field(None, description="Pre-sanitization confidentiality level")
    sanitization_method: str = Field(..., description="Sanitization method (clear, purge, destroy)")
    sanitization_technique: str = Field(..., description="Sanitization technique")
    tool_used: str = Field(..., description="Tool used including version")
    verification_method: str = Field(..., description="Verification method")
    post_sanitization_confidentiality: Optional[str] = Field(None, description="Post-sanitization confidentiality level")
    post_sanitization_destination: Optional[str] = Field(None, description="Post-sanitization destination")

class CertificateResponse(BaseModel):
    certificate_id: str
    pdf_url: str
    created_at: str
    user_id: str
    device_model: str
    message: str

def generate_pdf_certificate(details: SanitizationDetails, certificate_id: str, user_email: str) -> bytes:
    """Generate PDF certificate with user information"""
    
    print("📄 Starting PDF generation...")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.spaceAfter = 6
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("MEDIA SANITIZATION CERTIFICATE", title_style))
    story.append(Spacer(1, 12))
    
    # Certificate ID, Date, and User Info
    cert_info = [
        ['Certificate ID:', certificate_id],
        ['Date Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")],
        ['Authorized By:', user_email],
        ['Organization:', 'Media Sanitization Department']
    ]
    cert_table = Table(cert_info, colWidths=[2*inch, 3*inch])
    cert_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(cert_table)
    story.append(Spacer(1, 20))
    
    # Device Information
    story.append(Paragraph("DEVICE INFORMATION", heading_style))
    device_data = [
        ['Manufacturer:', details.manufacturer],
        ['Model:', details.model],
        ['Serial Number:', details.serial_number],
        ['Property Number:', details.property_number or 'N/A'],
        ['Media Type:', details.media_type],
        ['Media Source:', details.media_source],
    ]
    
    device_table = Table(device_data, colWidths=[2.5*inch, 3.5*inch])
    device_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
    ]))
    story.append(device_table)
    story.append(Spacer(1, 20))
    
    # Sanitization Information
    story.append(Paragraph("SANITIZATION INFORMATION", heading_style))
    sanitization_data = [
        ['Pre-Sanitization Confidentiality:', details.pre_sanitization_confidentiality or 'N/A'],
        ['Sanitization Method:', details.sanitization_method],
        ['Sanitization Technique:', details.sanitization_technique],
        ['Tool Used:', details.tool_used],
        ['Verification Method:', details.verification_method],
        ['Post-Sanitization Confidentiality:', details.post_sanitization_confidentiality or 'N/A'],
        ['Post-Sanitization Destination:', details.post_sanitization_destination or 'N/A'],
    ]
    
    sanitization_table = Table(sanitization_data, colWidths=[2.5*inch, 3.5*inch])
    sanitization_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
    ]))
    story.append(sanitization_table)
    story.append(Spacer(1, 40))
    
    # Certification Statement
    story.append(Paragraph("CERTIFICATION", heading_style))
    cert_statement = f"""
    This certificate confirms that the above-mentioned media has been sanitized according to the 
    specified method and technique. The sanitization process has been verified using the indicated 
    verification method. This certificate serves as official documentation of the media sanitization 
    process and was authorized by {user_email}.
    """
    story.append(Paragraph(cert_statement, normal_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    print("📄 PDF generation completed!")
    return buffer.getvalue()

@app.post("/generate-certificate", response_model=CertificateResponse)
async def generate_certificate(
    details: SanitizationDetails, 
    authorization: str = Header(None)
):
    """Generate a sanitization certificate PDF with user authentication"""
    
    try:
        # Extract token from Authorization header
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        
        # Verify user
        user_info = supabase.verify_user(token)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        user_id = user_info["id"]
        user_email = user_info.get("email", "unknown@example.com")
        
        print(f"🚀 Starting certificate generation for user: {user_email}")
        print(f"📋 Details received: {details.model_dump()}")
        
        # Generate unique certificate ID
        certificate_id = str(uuid.uuid4())
        print(f"🆔 Generated certificate ID: {certificate_id}")
        
        # Generate PDF with user info
        pdf_bytes = generate_pdf_certificate(details, certificate_id, user_email)
        print(f"📄 PDF size: {len(pdf_bytes)} bytes")
        
        # Create filename with user and device info
        safe_model = details.model.replace(" ", "_").replace("/", "_")
        filename = f"cert_{user_id}_{safe_model}_{certificate_id}.pdf"
        print(f"📂 Filename: {filename}")
        
        # Upload to Supabase Storage
        print("📤 Uploading to Supabase storage...")
        upload_response = supabase.upload_file("certificates", filename, pdf_bytes)
        
        if upload_response.status_code not in [200, 201]:
            print(f"❌ Upload failed: {upload_response.status_code} - {upload_response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to upload PDF: {upload_response.text}")
        
        print("✅ Upload successful!")
        
        # Get public URL
        pdf_url = supabase.get_public_url("certificates", filename)
        print(f"🔗 PDF URL: {pdf_url}")
        
        # Store certificate details in database with user association
        certificate_data = {
            "certificate_id": certificate_id,
            "user_id": user_id,
            "user_email": user_email,
            "manufacturer": details.manufacturer,
            "model": details.model,
            "serial_number": details.serial_number,
            "property_number": details.property_number,
            "media_type": details.media_type,
            "media_source": details.media_source,
            "pre_sanitization_confidentiality": details.pre_sanitization_confidentiality,
            "sanitization_method": details.sanitization_method,
            "sanitization_technique": details.sanitization_technique,
            "tool_used": details.tool_used,
            "verification_method": details.verification_method,
            "post_sanitization_confidentiality": details.post_sanitization_confidentiality,
            "post_sanitization_destination": details.post_sanitization_destination,
            "pdf_url": pdf_url,
            "created_at": datetime.now().isoformat()
        }
        
        print("💾 Saving to database...")
        # Insert into database
        db_response = supabase.insert_record("certificates", certificate_data)
        
        if db_response.status_code not in [200, 201]:
            print(f"❌ Database save failed: {db_response.status_code} - {db_response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to store certificate in database: {db_response.text}")
        
        print("✅ Database save successful!")
        
        result = CertificateResponse(
            certificate_id=certificate_id,
            pdf_url=pdf_url,
            created_at=datetime.now().isoformat(),
            user_id=user_id,
            device_model=details.model,
            message="Certificate generated and stored successfully"
        )
        
        print(f"🎉 Success! Returning: {result.model_dump()}")
        return result
        
    except Exception as e:
        error_msg = f"Error generating certificate: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/my-certificates")
async def get_my_certificates(authorization: str = Header(None), limit: int = 10, offset: int = 0):
    """Get all certificates for the authenticated user"""
    
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        user_info = supabase.verify_user(token)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        user_id = user_info["id"]
        
        response = supabase.select_records(
            "certificates", 
            {"user_id": user_id}, 
            limit=limit, 
            offset=offset
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Database error: {response.text}")
        
        data = response.json()
        
        return {
            "user_id": user_id,
            "certificates": data,
            "count": len(data)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving certificates: {str(e)}")

@app.get("/certificates-by-device/{model}")
async def get_certificates_by_device(model: str, authorization: str = Header(None)):
    """Get all certificates for a specific device model for the authenticated user"""
    
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        user_info = supabase.verify_user(token)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        user_id = user_info["id"]
        
        response = supabase.select_records(
            "certificates", 
            {"user_id": user_id, "model": model}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Database error: {response.text}")
        
        data = response.json()
        
        if not data:
            raise HTTPException(status_code=404, detail=f"No certificates found for device model: {model}")
        
        return {
            "device_model": model,
            "manufacturer": data[0]['manufacturer'] if data else "Unknown",
            "total_certificates": len(data),
            "certificates": data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving device certificates: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Authenticated Media Sanitization Certificate Generator API", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/user-info")
async def get_user_info(authorization: str = Header(None)):
    """Get current user information"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        user_info = supabase.verify_user(token)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        return {
            "user_id": user_info["id"],
            "email": user_info.get("email"),
            "authenticated": True
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)