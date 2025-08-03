# 🚀 Server Deployment Guide - 165.22.208.62:5004

## 🔧 Pre-configured Settings

Your application is now configured for:
- **Server IP**: 165.22.208.62
- **Port**: 5004
- **URL**: http://165.22.208.62:5004

## 📋 Deployment Steps

### 1. Upload to Server
```bash
# Upload project to your server
scp -r Suraksha-Final user@165.22.208.62:/opt/
```

### 2. SSH and Deploy
```bash
# SSH to server
ssh user@165.22.208.62

# Navigate to project
cd /opt/Suraksha-Final

# Make deploy script executable
chmod +x deploy.sh

# Run deployment (will prompt for MySQL password)
./deploy.sh
```

### 3. What the Deploy Script Does
- ✅ Installs all system dependencies
- ✅ Creates Python virtual environment
- ✅ Installs Python packages
- ✅ Prompts for your MySQL root password
- ✅ Creates database and imports schema
- ✅ Configures Nginx for port 5004
- ✅ Sets up Supervisor process management
- ✅ Configures firewall
- ✅ Starts application on port 5004

### 4. Access Application
After successful deployment:
- **URL**: http://165.22.208.62:5004
- **Admin Login**: username=`admin`, password=`admin123`
- **Professional Login**: username=`demo`, password=`9876543210`

## 🔧 Troubleshooting

### If login doesn't work:
```bash
# Check application logs
sudo supervisorctl tail -f suraksha

# Check if app is running
sudo supervisorctl status suraksha

# Restart application
sudo supervisorctl restart suraksha
```

### If database issues:
```bash
# Test database connection
mysql -u root -p suraksha_db -e "SELECT username, role FROM users;"

# Re-import schema if needed
mysql -u root -p suraksha_db < /opt/Suraksha-Final/database/schema.sql
```

## 🔒 Post-Deployment Security
1. **Change default passwords** after first login
2. **Setup SSL** with `./setup_ssl.sh` (optional)
3. **Configure firewall** (done automatically)

## ✅ Ready to Deploy!
Everything is configured for your server. Just run the deploy script and it will handle everything automatically!
