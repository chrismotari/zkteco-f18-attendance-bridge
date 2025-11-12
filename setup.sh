#!/bin/bash

# Django Attendance Bridge - Initial Setup Script

echo "=========================================="
echo "Django Attendance Bridge - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env file with your configuration!"
    echo "  - Set DJANGO_SECRET_KEY"
    echo "  - Set CRM_API_URL"
    echo "  - Set CRM_API_TOKEN"
else
    echo ".env file already exists"
fi
echo ""

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs
echo ""

# Run migrations
echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate
echo ""

# Create superuser prompt
echo "=========================================="
echo "Create Django Admin Superuser"
echo "=========================================="
read -p "Do you want to create a superuser now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi
echo ""

# Make scripts executable
echo "Making scripts executable..."
chmod +x start_server.sh start_worker.sh start_beat.sh
echo ""

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Ensure Redis is running: redis-cli ping"
echo "3. Start the application:"
echo "   Terminal 1: ./start_server.sh"
echo "   Terminal 2: ./start_worker.sh"
echo "   Terminal 3: ./start_beat.sh"
echo ""
echo "4. Access Django Admin: http://localhost:8000/admin"
echo "5. Add your ZKTeco devices in the admin"
echo "6. Test device connection: python manage.py test_device --all"
echo ""
echo "For detailed instructions, see README.md and SETUP.md"
echo ""
