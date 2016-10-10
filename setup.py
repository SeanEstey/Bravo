import os


def copy_files():
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')
    os.system('mkdir /var/www/bravo/php')
    os.system('cp php/* /var/www/bravo/php')

    os.system('cp virtual_host/default /etc/nginx/sites-enabled/')
    os.system('service nginx restart')

    os.system('cp logrotate/bravo /etc/logrotate.d/')
    os.system('logrotate --force /etc/logrotate.d/bravo')

if __name__ == "__main__":
    copy_files()
