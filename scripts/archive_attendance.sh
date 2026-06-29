#!/bin/bash
if [ -d "/var/www/Shafmet" ]; then
    # Remote server environment
    cd /var/www/Shafmet
    env/bin/python manage.py archive_attendance >> /var/www/Shafmet/archive_cron.log 2>&1
else
    # Local laptop environment
    cd /home/ubuntu/Documents/Loyxalar/Shafmet/shafmet-Beckend
    .venv/bin/python manage.py archive_attendance >> /home/ubuntu/Documents/Loyxalar/Shafmet/shafmet-Beckend/archive_cron.log 2>&1
fi
