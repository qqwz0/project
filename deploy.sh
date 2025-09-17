#!/bin/bash
set -e

if [[ $EUID -eq 0 ]]; then
   echo "ERROR: This script should not be run as root"
   exit 1
fi

echo "Updating package list..."
sudo apt update

echo "Removing old Docker versions to avoid conflicts..."
sudo apt remove -y docker docker-engine docker.io containerd runc || true

echo "Installing dependencies for Docker..."
sudo apt install -y ca-certificates curl gnupg lsb-release git || true

echo "Adding Docker GPG key and repo..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "Updating package list again..."
sudo apt update

echo "Installing Docker and Docker Compose..."
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin curl

echo "Adding user to docker group..."
sudo usermod -aG docker $USER

echo "Starting and enabling Docker service..."
sudo systemctl enable docker --now

echo "Waiting for Docker to start..."
sleep 5

echo "Checking Docker version..."
docker --version || (echo "ERROR: Docker not installed properly" && exit 1)

PROJECT_DIR="/opt/mysite"
REPO_URL="https://github.com/qqwz0/project.git"
BRANCH="render-deploy"

echo "Setting up project in $PROJECT_DIR..."

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Cloning repository from branch $BRANCH..."
    sudo git clone -b $BRANCH $REPO_URL $PROJECT_DIR
    sudo chown -R $USER:$USER $PROJECT_DIR
else
    echo "Updating existing repository..."
    cd $PROJECT_DIR
    sudo git reset --hard HEAD
    sudo git clean -fd
    sudo git fetch origin
    sudo git checkout $BRANCH
    sudo git pull origin $BRANCH
    sudo chown -R $USER:$USER $PROJECT_DIR
fi

cd $PROJECT_DIR

echo "Stopping any existing containers..."
docker compose down --remove-orphans || true

echo "Building and starting containers..."
docker compose up --build -d

echo "Waiting for containers to start..."
sleep 15

echo "Checking container status..."
docker compose ps

echo "Checking last 20 logs from web container..."
docker compose logs --tail=20 web

echo "Running migrations and collectstatic..."
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput

echo "Checking application availability..."
if curl -f http://localhost > /dev/null 2>&1; then
    echo "Application started successfully!"
else
    echo "WARNING: Application may not be ready yet. Try again in a few minutes."
fi

echo "Setting up cron job for conditional redeploy (only if changes exist)..."
CRON_CMD="cd $PROJECT_DIR && git fetch origin $BRANCH && if ! git diff --quiet HEAD origin/$BRANCH; then git pull origin $BRANCH && docker compose up --build -d && docker compose exec -T web python manage.py migrate --noinput && docker compose exec -T web python manage.py collectstatic --noinput; fi"
( crontab -l 2>/dev/null | grep -v "$CRON_CMD" ; echo "*/5 * * * * $CRON_CMD" ) | crontab -

echo ""
echo "Deployment complete!"
echo "Your application is available at: http://192.168.64.5"
