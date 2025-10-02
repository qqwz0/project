#!/bin/bash
# Скрипт для налаштування Postfix для кращої доставки пошти

echo "Налаштування Postfix для кращої доставки пошти..."

# Backup оригінального конфігу
sudo cp /etc/postfix/main.cf /etc/postfix/main.cf.backup

# Додати налаштування до main.cf
sudo tee -a /etc/postfix/main.cf << EOF

# Custom settings for better email delivery
myhostname = $(hostname)
mydomain = $(hostname -d 2>/dev/null || echo "localdomain")
myorigin = \$myhostname
inet_interfaces = loopback-only
mydestination = \$myhostname, localhost.\$mydomain, localhost
relayhost = 
mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128
mailbox_size_limit = 0
recipient_delimiter = +
inet_protocols = ipv4

# Better headers to avoid spam
always_add_missing_headers = yes
EOF

# Перезапустити Postfix
sudo systemctl restart postfix
sudo systemctl enable postfix

echo "Postfix налаштовано. Тестуємо відправку..."

# Тест відправки
echo "Test email from $(hostname) at $(date)" | mail -s "[$(hostname)] Test Email" -r "test@$(hostname)" kmrnkviktoria@gmail.com

echo "Тест відправлено. Перевірте пошту (включно зі спамом) через 2-3 хвилини."
echo "Також перевірте логи: sudo tail -f /var/log/mail.log"
