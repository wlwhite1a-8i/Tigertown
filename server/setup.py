"""Interactive one-time setup; passwords are entered privately in the terminal."""
from getpass import getpass
from pathlib import Path
import os
import secrets
from dotenv import set_key
from werkzeug.security import generate_password_hash

root=Path(__file__).resolve().parent.parent
path=root/'.env'
if path.exists():
    print('A .env file already exists. Edit it in VS Code to change settings; setup will not overwrite it.')
    raise SystemExit(0)
print('Tiger Town website setup\nUse the MySQL settings from your Workbench connection.\n')
host=input('MySQL host [127.0.0.1]: ').strip() or '127.0.0.1'
port=input('MySQL port [3306]: ').strip() or '3306'
if not port.isdigit() or not 1<=int(port)<=65535:raise SystemExit('Port must be a number between 1 and 65535.')
database=input('Database name [tigertown]: ').strip() or 'tigertown'
user=input('MySQL username [root]: ').strip() or 'root'
password=getpass('MySQL password (typing is hidden): ')
while True:
    admin=getpass('Choose a website administrator password (at least 12 characters): ')
    if len(admin)<12 or len(admin)>200:
        print('Use between 12 and 200 characters.');continue
    if admin!=getpass('Confirm administrator password: '):
        print('Passwords did not match. Try again.');continue
    break
values={'DB_HOST':host,'DB_PORT':port,'DB_NAME':database,'DB_USER':user,'DB_PASSWORD':password,
        'ADMIN_PASSWORD_HASH':generate_password_hash(admin),'APP_SECRET_KEY':secrets.token_hex(32),
        'ALLOWED_HOSTS':'localhost,127.0.0.1,[::1]','COOKIE_SECURE':'false','PORT':'5000'}
# Create owner-readable only. Never put this file inside the frontend folder.
fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
os.close(fd)
for key,value in values.items():set_key(path,key,value,quote_mode='always')
print('\nSettings saved. Start the website: python server/server.py\nThen open http://127.0.0.1:5000 in your browser.')
