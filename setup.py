import os


def copy_files():
    # PHP
    os.system('mkdir /var/www')
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')
    os.system('mkdir /var/www/bravo/php')
    os.system('mkdir /var/www/bravo/php/lib')
    os.system('cp -avr php /var/www/bravo/')

    os.system('chown -R www-data:www-data /var/www/bravo/logs')
    #os.system('chmod +x

    os.system('cp virtual_host/default /etc/nginx/sites-enabled/')
    os.system('service nginx restart')

    os.system('cp logrotate/bravo /etc/logrotate.d/')
    os.system('logrotate --force /etc/logrotate.d/bravo')

if __name__ == "__main__":
    copy_files()
