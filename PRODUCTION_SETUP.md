# SURAKSHA Production Setup Guide

## Server: 165.22.208.62:5004

### 1. Database Setup
```sql
CREATE DATABASE suraksha_db;
CREATE USER 'suraksha_user'@'localhost' IDENTIFIED BY 'secure_password_123';
GRANT ALL PRIVILEGES ON suraksha_db.* TO 'suraksha_user'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Run Database Schema
```bash
mysql -u suraksha_user -p suraksha_db < database/schema.sql
```

### 3. Environment Configuration
The `.env` file is already configured for production:
- Host: 0.0.0.0 (all interfaces)
- Port: 5004
- Database: MySQL with secure credentials
- Debug: Disabled
- Flask Environment: Production

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Start Application
```bash
python app.py
```

### 6. Access Application
- URL: http://165.22.208.62:5004
- Admin Login: admin/admin
- Test the complete functionality

### 7. Recent Fixes Applied
✅ Export Excel functionality (date conversion fixed)
✅ Export PDF functionality  
✅ Add new trainee/training/professional (connection.commit() added)
✅ Edit training functionality
✅ Database viewer navigation (/expdata endpoint)
✅ SSIPMT logo integration (using ssipmt.jpg)
✅ Removed add buttons from database viewer
✅ All CRUD operations working

### 8. Application Features
- Admin Dashboard with full CRUD operations
- Medical Professional Dashboard  
- Database Viewer with export capabilities
- SSIPMT Branding Integration
- Training Management System
- Responsive UI Design

### 9. Security Notes
- Change SECRET_KEY in production
- Update database password
- Enable HTTPS if available
- Configure firewall for port 5004

## Ready for Git Push and Deployment! 🚀
