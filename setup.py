import os

if __name__ == "__main__":
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')
    os.system('chown -R www-data:root /var/www/bravo/logs')
    os.system('cp virtual_host/default /etc/nginx/sites-enabled/')
    os.system('service nginx restart')
    os.system('cp logrotate/bravo /etc/logrotate.d/')
    os.system('logrotate --force /etc/logrotate.d/bravo')
