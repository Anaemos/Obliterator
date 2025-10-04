# Obliterator

**A secure, cross-platform data wiping solution for safe e-waste management.**  
Built for **Smart India Hackathon (SIH)**, Obliterator addresses the critical challenge of **data security in electronic waste recycling**.

---

## Background

India generates over **1.75 million tonnes of e-waste annually**, yet millions of laptops and smartphones remain hoarded in homes and offices.  
The biggest reason: **fear of data breaches**.  

Most users hesitate to recycle or resell their devices because:
- Sensitive data might be recovered,
- Existing wiping tools are too **complex, expensive, or unverifiable**.  

As a result, more than **₹50,000 crore worth of IT assets** lie unused — harming the circular economy and contributing to environmental risks.

---

## Problem Statement

Design and prototype a **secure, cross-platform data wiping application** that:

- Securely erases all user data, including hidden storage (HPA/DCO, SSD sectors).  
- Generates a **digitally signed, tamper-proof wipe certificate** (PDF + JSON).  
- Offers an **intuitive one-click GUI**, accessible to everyday users.  
- Works offline (via **bootable ISO/USB**) for devices without OS access.  
- Enables **third-party verification** of wipe status.  
- Aligns with **NIST SP 800-88** standards for data sanitization.  

---

## Impact

- Builds **user confidence** in recycling & resale of devices.  
- Reduces hoarding of IT assets by making disposal safe.  
- Promotes **trust, transparency, and accountability** in IT asset disposal.  
- Supports **India’s circular economy** and sustainable e-waste management.  

---

## Technical Overview

Obliterator consists of:
- **GUI Entry Point** → `obliterator_gui.py`  
- **Authentication Layer** → `login_system.py` (Supabase-based)  
- **Data Wiping Engine** → secure erasure methods across drives/sectors  
- **Certificate Generator** → creates tamper-proof wipe reports in **PDF/JSON**
- **To test run obliterator_gui.py directly  

The prototype was integrated into **Puppy Linux (Bookwormpup)** ISO for:
- **Bootable USB deployment**  
- **Virtual Machine demo environment (Vbox)**  

---

## 🚀 Getting Started

### Installation

```bash
git clone https://github.com/Anaemos/Obliterator.git
cd Obliterator
