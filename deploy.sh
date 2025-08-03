#!/bin/bash

# Suraksha Medical Training System - Production Deployment Script
# Automated deployment for Linux servers

set -e  # Exit on any error

echo "=== Suraksha Medical Training System - Production Deployment ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Get application directory
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

print_header "Setting up Suraksha Medical Training System in: $APP_DIR"
echo ""

# Step 1: Update system packages
print_header "Step 1: Updating system packages"
sudo apt update && sudo apt upgrade -y

# Step 2: Install required system packages
print_header "Step 2: Installing system dependencies"
sudo apt install -y python3 python3-pip python3-venv mysql-client nginx supervisor

# Step 3: Create virtual environment
print_header "Step 3: Setting up Python environment"
python3 -m venv venv
source venv/bin/activate

# Step 4: Install Python dependencies
print_header "Step 4: Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Setup environment variables
print_header "Step 5: Setting up environment configuration"
if [ ! -f .env ]; then
    cp .env.example .env
    
    # Generate secure secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/change-this-to-a-very-secure-random-key-in-production/$SECRET_KEY/" .env
    
    chmod 600 .env
    print_status "Environment file created with secure secret key"
else
    print_warning ".env file already exists, skipping creation"
fi

# Step 6: Setup MySQL database
print_header "Step 6: Setting up database"
DB_PASSWORD="Ssipmt@2025DODB"

# Test database connection
print_status "Testing database connection..."
if mysql -h 127.0.0.1 -u root -p"$DB_PASSWORD" -e "SELECT 1;" >/dev/null 2>&1; then
    print_status "Database connection successful"
else
    print_error "Failed to connect to database. Please check your MySQL server and credentials."
    exit 1
fi

# Create database and import schema
print_status "Creating database and importing schema..."
mysql -h 127.0.0.1 -u root -p"$DB_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS suraksha_db;"
mysql -h 127.0.0.1 -u root -p"$DB_PASSWORD" suraksha_db < database/schema.sql

print_status "Database setup completed successfully"

# Step 7: Create Nginx configuration
print_header "Step 7: Setting up Nginx"
sudo tee /etc/nginx/sites-available/suraksha << EOF
server {
    listen 80;
    server_name _;  # Replace with your domain
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
    
    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
    
    client_max_body_size 20M;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/suraksha /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

print_status "Nginx configured and started"

# Step 8: Create Supervisor configuration
print_header "Step 8: Setting up process management"
sudo tee /etc/supervisor/conf.d/suraksha.conf << EOF
[program:suraksha]
command=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 --timeout 60 --keep-alive 5 wsgi:app
directory=$APP_DIR
user=$(whoami)
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/suraksha.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin"
EOF

# Create logs directory
mkdir -p logs

# Update Supervisor and start application
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start suraksha

print_status "Application started with Supervisor"

# Step 9: Setup firewall
print_header "Step 9: Configuring firewall"
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

print_status "Firewall configured"

# Step 10: Create backup script
print_header "Step 10: Setting up automated backups"
tee backup.sh << 'EOF'
#!/bin/bash
# Backup script for Suraksha Medical Training System

BACKUP_DIR="$HOME/suraksha_backups"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p $BACKUP_DIR

# Backup database
mysqldump -h 127.0.0.1 -u root -p'Ssipmt@2025DODB' suraksha_db > $BACKUP_DIR/suraksha_db_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/suraksha_app_$DATE.tar.gz -C $(dirname $APP_DIR) $(basename $APP_DIR) --exclude=venv --exclude=__pycache__ --exclude=*.pyc --exclude=logs

echo "Backup completed: $BACKUP_DIR/suraksha_*_$DATE.*"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "suraksha_*" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab for daily backup
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -

print_status "Backup script created and scheduled"

# Step 11: Create SSL setup script
print_header "Step 11: Creating SSL certificate setup script"
tee setup_ssl.sh << 'EOF'
#!/bin/bash
# SSL Certificate setup using Let's Encrypt

echo "Setting up SSL certificate with Let's Encrypt..."
sudo apt install -y certbot python3-certbot-nginx

echo "Please enter your domain name (e.g., example.com):"
read domain_name

if [ ! -z "$domain_name" ]; then
    # Update Nginx configuration with domain name
    sudo sed -i "s/server_name _;/server_name $domain_name www.$domain_name;/" /etc/nginx/sites-available/suraksha
    sudo nginx -t && sudo systemctl reload nginx
    
    # Get SSL certificate
    sudo certbot --nginx -d "$domain_name" -d "www.$domain_name"
    
    # Setup auto-renewal
    echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
    
    echo "SSL certificate installed successfully!"
else
    echo "No domain name provided. SSL setup skipped."
fi
EOF

chmod +x setup_ssl.sh

print_status "SSL setup script created"

# Final status check
print_header "Step 12: Final verification"
sleep 3

if sudo supervisorctl status suraksha | grep -q RUNNING; then
    echo ""
    echo "======================================"
    echo -e "${GREEN}🎉 DEPLOYMENT SUCCESSFUL! 🎉${NC}"
    echo "======================================"
    echo ""
    print_status "Application is running successfully!"
    print_status "Nginx is configured and running"
    print_status "Supervisor is managing the application"
    print_status "Database is set up and connected"
    print_status "Automated backups are scheduled"
    echo ""
    echo -e "${BLUE}🌐 Access your application:${NC}"
    echo "   http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip')"
    echo ""
    echo -e "${BLUE}🔑 Default login credentials:${NC}"
    echo "   Admin: username=admin, password=admin123"
    echo "   Professional: username=demo, password=9876543210"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT NEXT STEPS:${NC}"
    echo "1. Change default passwords after first login"
    echo "2. Configure your domain name in Nginx"
    echo "3. Run ./setup_ssl.sh to enable HTTPS"
    echo "4. Test all functionality thoroughly"
    echo ""
    echo -e "${BLUE}🔧 Useful commands:${NC}"
    echo "   Check logs: sudo supervisorctl tail -f suraksha"
    echo "   Restart app: sudo supervisorctl restart suraksha"
    echo "   Check status: sudo supervisorctl status"
    echo "   Backup data: ./backup.sh"
    echo ""
else
    echo ""
    echo "======================================"
    echo -e "${RED}❌ DEPLOYMENT FAILED ❌${NC}"
    echo "======================================"
    print_error "Application failed to start. Check logs:"
    echo "sudo supervisorctl tail suraksha"
    exit 1
fi

print_status "Deployment completed successfully!"
EOF
EOF
