#!/usr/bin/env python3
import json
import os
import io
import subprocess
import sys
from pathlib import Path

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]
YOUTUBE_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def write_secret(name, destination):
    data = json.loads(required(name))
    destination.write_text(json.dumps(data), encoding="utf-8")
    destination.chmod(0o600)


def download_drive_file(file_id, destination, credentials):
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    request = drive.files().get_media(fileId=file_id)
    with destination.open("wb") as output:
        downloader = MediaIoBaseDownload(output, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Drive download: {int(status.progress() * 100)}%")


def has_audio(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def make_title(topic, label):
    topic = " ".join(topic.split())
    label = " ".join(label.split()).title()
    title = f"Top 3 {topic} Football Edits 😭 {label} #football #shorts"
    return title[:100].rstrip()


def upload(video, title, channel, public_approval, token_path):
    privacy = "public" if public_approval.strip().upper() == "YES — UPLOAD PUBLICLY" else "private"
    creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPE)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": "#football #shorts", "categoryId": "17"},
            "status": {"privacyStatus": privacy},
        },
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    print(f"Uploaded to {channel} as {privacy}: https://youtu.be/{response['id']}")


def main():
    WORK.mkdir(exist_ok=True)
    service_path = WORK / "google-service-account.json"
    write_secret("GOOGLE_SERVICE_ACCOUNT_JSON", service_path)
    drive_creds = service_account.Credentials.from_service_account_file(str(service_path), scopes=DRIVE_SCOPE)
    clip3 = WORK / "clip3.mp4"
    clip2 = WORK / "clip2.mp4"
    download_drive_file(required("CLIP_3_FILE_ID"), clip3, drive_creds)
    download_drive_file(required("CLIP_2_FILE_ID"), clip2, drive_creds)
    if not has_audio(clip3) or not has_audio(clip2):
        raise RuntimeError("Submission stopped: both source clips must contain audio.")

    label3 = required("LABEL_3").upper()[:32]
    label2 = required("LABEL_2").upper()[:32]
    output = WORK / "finished-short.mp4"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render_short.py"), str(clip3), str(clip2), label3, label2, str(output)], check=True)

    channel = required("CHANNEL")
    secret_name = "YOUTUBE_LIFES_HIGHLIGHTS_TOKEN_JSON" if channel == "Life's Highlights" else "YOUTUBE_GOLDENBOOT_TOKEN_JSON"
    token_path = WORK / "youtube-token.json"
    write_secret(secret_name, token_path)
    upload(output, make_title(required("TOPIC"), label2), channel, required("PUBLIC_APPROVAL"), token_path)


if __name__ == "__main__":
    main()
