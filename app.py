import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from azure.storage.blob import BlobServiceClient, ContentSettings
from io import BytesIO
from urllib.parse import quote as url_quote
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# Azure Blob Storage config
STORAGE_CONNECTION_STRING = os.environ.get("STORAGE_CONNECTION_STRING")
INPUT_CONTAINER = "input-documents"
TRANSLATED_CONTAINER = "translated-documents"

blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

def get_supported_languages():
    """Fetch supported languages from Azure Translator API."""
    url = "https://api.cognitive.microsofttranslator.com/languages?api-version=3.0&scope=translation"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {code: info['name'] for code, info in data['translation'].items()}
    except Exception as e:
        # Fallback to common languages if API fails
        flash(f"Could not fetch language list: {str(e)}", "warning")
        return {
            "en": "English",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
            "am": "Amharic",
        }

@app.route("/", methods=["GET", "POST"])
def index():
    LANGUAGES = get_supported_languages()

    if request.method == "POST":
        uploaded_file = request.files.get("file")
        target_lang = request.form.get("language")

        if not uploaded_file or uploaded_file.filename == "":
            flash("Please select a file to upload.", "danger")
            return redirect(request.url)
        if target_lang not in LANGUAGES:
            flash("Invalid target language selected.", "danger")
            return redirect(request.url)

        try:
            container_client = blob_service_client.get_container_client(INPUT_CONTAINER)
            blob_client = container_client.get_blob_client(uploaded_file.filename)

            content_settings = ContentSettings(content_type=uploaded_file.content_type)
            metadata = {"language": target_lang}

            blob_client.upload_blob(
                uploaded_file.stream.read(),
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata,
            )
            flash(f"File '{uploaded_file.filename}' uploaded successfully for translation to {LANGUAGES[target_lang]}.", "success")
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "danger")

        return redirect(url_for("index"))

    try:
        container_client = blob_service_client.get_container_client(TRANSLATED_CONTAINER)
        blobs = container_client.list_blobs()
        translated_files = [blob.name for blob in blobs]
    except Exception as e:
        translated_files = []
        flash(f"Failed to list translated documents: {str(e)}", "danger")

    return render_template("index.html", languages=LANGUAGES, translated_files=translated_files)

@app.route("/download/<filename>")
def download_file(filename):
    try:
        container_client = blob_service_client.get_container_client(TRANSLATED_CONTAINER)
        blob_client = container_client.get_blob_client(filename)
        stream = blob_client.download_blob()
        file_stream = BytesIO()
        file_stream.write(stream.readall())
        file_stream.seek(0)
        return send_file(file_stream, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Failed to download file: {str(e)}", "danger")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
