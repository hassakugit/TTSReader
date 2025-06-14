# main.py

import os
import io
import torch
import logging
import tempfile
import pdfplumber
from ebooklib import epub, ITEM_DOCUMENT
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from whisperspeech.pipeline import Pipeline

# --- Configuration and Initialization ---
# Setup logging
logging.basicConfig(level=logging.INFO)

# Check for CUDA availability
if torch.cuda.is_available():
    device = "cuda:0"
    torch_dtype = torch.float16
    logging.info("CUDA is available. Using GPU.")
else:
    device = "cpu"
    torch_dtype = torch.float32
    logging.info("CUDA not available. Using CPU.")

# Initialize the WhisperSpeech pipeline
# This will download the model on the first run, which can take time.
# In a Cloud Run environment, this happens during container startup or the first request.
try:
    pipe = Pipeline(s2a_ref='collabora/whisperspeech:s2a-q4-tiny-en+pl.model', device=device, torch_dtype=torch_dtype)
    logging.info("WhisperSpeech pipeline initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize WhisperSpeech pipeline: {e}")
    pipe = None

# Initialize Flask App
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit

# --- Helper Functions ---
def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file stream."""
    text = ""
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_txt(file_stream):
    """Extracts text from a TXT file stream."""
    return file_stream.read().decode('utf-8')

def extract_text_from_epub(file_path):
    """Extracts text from an EPUB file."""
    book = epub.read_epub(file_path)
    text = ""
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        # A simple way to get content, might need more robust HTML parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text += soup.get_text() + "\n"
    return text

def process_text_to_speech(text_to_process):
    """Generates audio from text using WhisperSpeech."""
    if not pipe:
        raise RuntimeError("TTS Pipeline is not available.")
    if not text_to_process or not text_to_process.strip():
        raise ValueError("Input text is empty.")
    
    # Generate audio
    # Using a temporary file for the output is robust for serverless environments
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        audio_path = tmpfile.name
        logging.info(f"Generating audio for text: '{text_to_process[:100]}...'")
        pipe.generate_to_file(audio_path, text_to_process, lang='en')
        logging.info(f"Audio generated and saved to {audio_path}")
        return audio_path

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Handles the form submission for TTS conversion."""
    text_input = request.form.get('text_input', '').strip()
    file_input = request.files.get('file_input')
    
    text_to_process = ""

    if file_input and file_input.filename != '':
        filename = secure_filename(file_input.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        try:
            if file_ext == '.pdf':
                text_to_process = extract_text_from_pdf(file_input.stream)
            elif file_ext == '.txt':
                text_to_process = extract_text_from_txt(file_input.stream)
            elif file_ext == '.epub':
                # EbookLib needs a file path, so we save it temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                    file_input.save(tmp_file.name)
                    text_to_process = extract_text_from_epub(tmp_file.name)
                os.unlink(tmp_file.name) # Clean up the temp file
            else:
                return jsonify({"error": f"Unsupported file type: {file_ext}"}), 400
        except Exception as e:
            logging.error(f"Error processing file {filename}: {e}")
            return jsonify({"error": f"Failed to read or process the file: {e}"}), 500

    elif text_input:
        text_to_process = text_input
    
    if not text_to_process:
        return jsonify({"error": "No text provided from input or file."}), 400
        
    try:
        audio_file_path = process_text_to_speech(text_to_process)
        
        # Send the file back to the user and clean up afterwards
        @app.after_request
        def remove_file(response):
            try:
                os.remove(audio_file_path)
            except Exception as error:
                app.logger.error("Error removing or closing audio file: %s", error)
            return response
            
        return send_file(
            audio_file_path,
            mimetype='audio/wav',
            as_attachment=False # False to play in browser, True to force download
        )

    except Exception as e:
        logging.error(f"An error occurred during TTS processing: {e}")
        return jsonify({"error": str(e)}), 500

# --- Main Entry Point ---
if __name__ == '__main__':
    # This is for local development only.
    # For production, we'll use gunicorn via the Dockerfile.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
