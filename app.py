import io
import os
import json
import pickle
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from flask import Flask, request, render_template, send_file
from PIL import Image

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly"]

# Add your client ID and client secret here
CLIENT_ID = "CLIENT_ID"
CLIENT_SECRET = "CLIENT_SECRET"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly"]

# The file that will store the user's credentials
CREDENTIALS_FILE = "credentials.json"


def get_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        creds = Credentials.from_authorized_user_file(filename=CREDENTIALS_FILE, scopes=SCOPES)
    else:
        flow = InstalledAppFlow.from_client_config(
            client_config={
                "installed": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uris": [REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
        )

        creds = flow.run_local_server(port=0)
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(json.loads(creds.to_json()), f)

    return creds


def create_google_photos_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("photoslibrary", "v1", credentials=creds, static_discovery=False)


def list_albums(service):
    album_list = []
    next_page_token = None

    while True:
        results = service.albums().list(
            pageSize=50, pageToken=next_page_token, fields="nextPageToken,albums(id,title)"
        ).execute()
        items = results.get("albums", [])

        if not items:
            break

        for item in items:
            title = item["title"]
            album_list.append(title)

        next_page_token = results.get("nextPageToken")

        if not next_page_token:
            break

    return album_list


@app.route('/')
def get_album_list():
    service = create_google_photos_service()

    results = service.albums().list(
        pageSize=10, fields="nextPageToken,albums(id,title,mediaItemsCount)").execute()
    items = results.get('albums', [])

    album_options = []
    for item in items:
        title = item['title']
        album_id = item['id']
        num_photos = item.get('mediaItemsCount', 0)
        album_options.append({'title': title, 'id': album_id, 'num_photos': num_photos})

    num_photos = None
    album_name = None
    photo_thumbnails = []
    num_columns = 10  # Default value is 10

    if request.method == 'GET':
        album_id = request.args.get('album_id')
        if album_id:
            results = service.mediaItems().search(
                body={
                    "albumId": album_id,
                    "pageSize": 1,
                }
            ).execute()
            num_photos = results.get('totalMediaItems', 0)
            album_name = [option["title"] for option in album_options if option["id"] == album_id][0]

            # Fetch photos with pagination
            next_page_token = None
            photo_thumbnails = []

            while True:
                results = service.mediaItems().search(
                    body={
                        "albumId": album_id,
                        "pageSize": 100,
                        "pageToken": next_page_token,
                    }
                ).execute()

                photos = results.get('mediaItems', [])
                photo_thumbnails.extend([photo['baseUrl'] for photo in photos])

                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break

            photo_thumbnails.reverse() # reverse the order of the photos

            num_columns = int(request.args.get('num_columns', 3))  # Default value is 3 if not provided
            print(photo_thumbnails)

    return render_template('index.html', album_options=album_options, num_photos=num_photos, album_name=album_name, photo_thumbnails=photo_thumbnails, num_columns=num_columns)

@app.route('/album')
def get_album_photos():
    album_id = request.args.get('album_id')
    service = create_google_photos_service()
    results = service.mediaItems().search(
        body={
            "albumId": album_id,
            "pageSize": 100,
        }
    ).execute()
    photos = results.get('mediaItems', [])
    num_photos = len(photos)
    return f'Total number of photos in the album: {num_photos}'

@app.route('/export', methods=['POST'])
def export():
    data = request.get_json()
    images = data['images']
    num_columns = int(data['num_columns'])

    rows = -(-len(images) // num_columns)
    canvas_width = num_columns * 200
    canvas_height = rows * 200

    canvas = Image.new('RGB', (canvas_width, canvas_height))
    
    for idx, url in enumerate(images):
        response = requests.get(url)
        img = Image.open(io.BytesIO(response.content))
        row = idx // num_columns
        col = idx % num_columns
        x = col * 200
        y = row * 200
        canvas.paste(img, (x, y))

    img_bytes = io.BytesIO()
    canvas.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/jpeg', as_attachment=True, download_name='album_export.jpg')


if __name__ == "__main__":
    app.run()