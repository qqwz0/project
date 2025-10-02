#!/bin/bash
set -e

# Configuration
LOG_FILE="/opt/mysite/cron.log"
EMAIL="kmrnkviktoria@gmail.com"
PROJECT_DIR="/opt/mysite"
BRANCH="master"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Start logging
{
    log "=== Cron job started ==="
    
    # Change to project directory
    cd "$PROJECT_DIR" || {
        log "ERROR: Cannot change to project directory $PROJECT_DIR"
        exit 1
    }
    
    # Git operations
    log "Fetching latest changes from origin..."
    if git fetch origin "$BRANCH"; then
        log "Git fetch completed successfully"
    else
        log "ERROR: Git fetch failed"
        exit 1
    fi
    
    # Check if there are changes
    if git diff --quiet HEAD origin/"$BRANCH"; then
        log "No changes detected, deployment not needed"
        exit 0
    fi
    
    log "Changes detected, starting deployment..."
    
    # Pull latest changes
    if git pull origin "$BRANCH"; then
        log "Git pull completed successfully"
    else
        log "ERROR: Git pull failed"
        exit 1
    fi
    
    # Docker operations
    log "Building and starting Docker containers..."
    docker-compose down
    docker-compose up --build -d
    
    # Wait for services to start
    log "Waiting for services to start..."
    sleep 30
    
    # Check if containers are running
    log "Checking if containers are running..."
    sleep 5  # Додаткова пауза для запуску контейнерів
    
    if ! docker-compose ps | grep -q "Up"; then
        log "ERROR: Docker containers failed to start"
        docker-compose logs >> "$LOG_FILE"
        exit 1
    fi
    log "Docker containers are running successfully"
    
    # Django operations
    log "Running Django migrations..."
    if docker-compose exec -T web python manage.py migrate --noinput; then
        log "Migrations completed successfully"
    else
        log "ERROR: Migrations failed"
        docker-compose logs web >> "$LOG_FILE"
        exit 1
    fi
    
    log "Collecting static files..."
    if docker-compose exec -T web python manage.py collectstatic --noinput --clear; then
        log "Static files collected successfully"
    else
        log "ERROR: Collectstatic failed"
        docker-compose logs web >> "$LOG_FILE"
        exit 1
    fi
    
    # Restart nginx
    log "Restarting nginx..."
    if docker-compose restart nginx; then
        log "Nginx restarted successfully"
    else
        log "ERROR: Failed to restart nginx"
        exit 1
    fi
    
    # Health check
    log "Performing health check..."
    sleep 15  # Більше часу для повного запуску
    
    # Перевіряємо чи відповідає додаток
    if curl -f -s http://localhost:8000 > /dev/null; then
        log "Health check passed - application is responding"
    else
        log "WARNING: Health check failed - application may not be responding correctly"
        # Не виходимо з помилкою, але логуємо попередження
        docker-compose logs web >> "$LOG_FILE"
    fi
    
    log "=== Cron job completed successfully ==="
    
} 2>&1 | tee -a "$LOG_FILE"

# Send email notification if mail is available
if command -v mail >/dev/null 2>&1; then
    # Check if log file exists
    if [ -f "$LOG_FILE" ]; then
        log "Attempting to send email notification to $EMAIL"
        
        # Create a proper email with headers to avoid spam
        {
            echo "Subject: [$(hostname)] Deployment Report $(date '+%Y-%m-%d %H:%M:%S')"
            echo "From: deployment@$(hostname)"
            echo "To: $EMAIL"
            echo "Content-Type: text/plain; charset=UTF-8"
            echo ""
            echo "=== DEPLOYMENT REPORT ==="
            echo "Server: $(hostname)"
            echo "Date: $(date)"
            echo "Project: $PROJECT_DIR"
            echo "Branch: $BRANCH"
            echo ""
            echo "=== LOG DETAILS ==="
            cat "$LOG_FILE"
        } | sendmail "$EMAIL"
        
        # Also try with mail command as backup
        mail -s "[$(hostname)] Deployment $(date '+%H:%M')" -r "deployment@$(hostname)" "$EMAIL" < "$LOG_FILE"
        
        log "Email notification sent to $EMAIL"
    else
        log "ERROR: Log file $LOG_FILE not found, sending simple notification"
        echo "Deployment completed on $(hostname) at $(date), but log file was not found." | \
        mail -s "[$(hostname)] Deployment Alert $(date '+%H:%M')" -r "deployment@$(hostname)" "$EMAIL"
    fi
else
    log "WARNING: Mail command not available, email notification skipped"
fi
