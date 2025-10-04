# 🔐 SecureWipe Pro - Login System

Professional authentication system for SecureWipe Pro data wiping application.

## 🎯 Quick Start

### 1. Activate Virtual Environment
```bash
cd securewipe_pro
source venv/bin/activate
```

### 2. Test the System
```bash
# Run basic tests
python test_login.py

# Run full login system
python login_system.py

# Run integration example
python main_app_example.py
```

## 📁 File Structure

```
securewipe_pro/
├── venv/                    # Virtual environment
├── login_system.py         # Main authentication system
├── config.json             # Supabase configuration
├── test_login.py           # Test script
├── main_app_example.py     # Integration example
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore file
├── README.md              # This file
└── logs/                  # Auto-generated logs
```

## 🔧 Configuration

Your Supabase configuration is already set up in `config.json`:
- **URL**: https://nhdwylbgcwrvbillwouy.supabase.co
- **Key**: Your anon public key

## ⚡ Features

- ✅ **Splash Screen** - Professional loading with connectivity checks
- ✅ **User Authentication** - Email/password login via Supabase
- ✅ **Session Management** - Secure local session storage with "Remember Me"
- ✅ **User Registration** - New account creation
- ✅ **Password Reset** - Email-based password recovery
- ✅ **Purple-Dark Theme** - Professional UI design
- ✅ **Security Features** - Input validation, error handling, logging
- ✅ **Cross-Platform** - Works on Linux, Debian, Puppy Linux

## 🔗 Integration

To integrate with your main data wiping application:

```python
from login_system import LoginSystem

def main():
    # Initialize login
    login_system = LoginSystem()
    
    # Authenticate user
    if login_system.authenticate_user():
        user_data = login_system.get_user_session()
        
        # Start your main application
        start_data_wiping_app(user_data)
    else:
        print("Authentication required")

def start_data_wiping_app(user_data):
    # Your main application code here
    print(f"User: {user_data['email']}")
    # Launch your data wiping GUI
```

## 🧪 Testing

Run tests to verify everything works:

```bash
# Basic system test
python test_login.py

# Test with GUI
python login_system.py

# Test integration
python main_app_example.py
```

## 🛡️ Security

- All communications use HTTPS
- Sessions encrypted locally
- No passwords stored locally
- Automatic session expiration
- Security event logging

## 🔍 Troubleshooting

### Common Issues:

1. **Import errors**: Make sure virtual environment is activated
   ```bash
   source venv/bin/activate
   ```

2. **Connection errors**: Check internet connection and Supabase status

3. **Configuration errors**: Verify `config.json` has correct Supabase credentials

4. **Tkinter errors**: Install python3-tk
   ```bash
   sudo apt install python3-tk
   ```

### Debug Mode:
```bash
# Run with debug logging
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from login_system import LoginSystem
login = LoginSystem()
login.authenticate_user()
"
```

## 📞 Support

- Check logs in `logs/app.log` for error details
- Verify Supabase project is active
- Ensure all dependencies are installed
- Test network connectivity

## 🚀 Next Steps

1. **Test the login system** with `python test_login.py`
2. **Integrate with your main app** using the example patterns
3. **Customize UI elements** (colors, text, logos) as needed
4. **Add your data wiping logic** to the authenticated application

The system is ready for integration with your main data wiping application!