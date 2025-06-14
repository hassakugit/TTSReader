# main.py

import os
import torch
import logging
import tempfile
import pdfplumber
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from TTS.api import TTS

# --- NEW: PyTorch Security Fix ---
# Newer versions of PyTorch have a security feature that prevents loading
# arbitrary classes. We need to explicitly trust the configuration class
# from the TTS model we are using.
from TTS.tts.configs.xtts_config import XttsConfig
torch.serialization.add_safe_globals([XttsConfig])
# --- End of New Code ---

# --- Configuration and Initialization ---
# Setup logging
logging.basicConfig(level=logging.INFO)

# Check for CUDA availability
if torch.cuda.is_available():
    gpu_enabled = True
    logging.info("CUDA is available. Using GPU.")
else:
    gpu_enabled = False
    logging.info("CUDA not available. Using CPU.")

# --- Lazy Initialization of the Model ---
tts_model = None

def get_tts_model():
    """Initializes and returns the TTS model, loading it only once."""
    global tts_model
    if tts_model is None:
        logging.info("TTS model not initialized. Loading Coqui-TTS model from local files...")
        try:
            # The model is already downloaded in the Docker image,
            # so this will be a very fast load from disk.
            model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
            tts_model = TTS(model_name, gpu=gpu_enabled)
            logging.info(f"Coqui-TTS model '{model_name}' initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Coqui-TTS model: {e}", exc_info=True)
            raise RuntimeError(f"Could not load TTS model: {e}")
    return tts_model

# Initialize Flask App
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit

# --- Helper Functions ---
def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file stream."""
    text = ""
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_txt(file_stream):
    """Extracts text from a TXT file stream."""
    return file_stream.read().decode('utf-8', errors='ignore')

def extract_text_from_epub(file_path):
    """Extracts text from an EPUB file."""
    book = epub.read_epub(file_path)
    text = ""
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text += soup.get_text() + "\n"
    return text

def process_text_to_speech(text_to_process):
    """Generates audio from text using Coqui-TTS."""
    model = get_tts_model()
    
    if not text_to_process or not text_to_process.strip():
        raise ValueError("Input text is empty.")
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        audio_path = tmpfile.name
        logging.info(f"Generating audio for text: '{text_to_process[:150]}...'")
        
        # Use a random speaker from the model's available speakers
        speaker_id = model.speaker_manager.get_random_speaker_id()
        if not speaker_id:
             # Fallback if no speakers are found for some reason
            all_speakers = model.speaker_manager.get_speaker_ids()
            if all_speakers:
                speaker_id = all_speakers[0]

        model.tts_to_file(
            text=text_to_process,
            file_path=audio_path,
            speaker=speaker_id,
            language='en'
        )
        
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
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                    file_input.save(tmp_file.name)
                    text_to_process = extract_text_from_epub(tmp_file.name)
                os.unlink(tmp_file.name)
            else:
                return jsonify({"error": f"Unsupported file type: {file_ext}"}), 400
        except Exception as e:
            logging.error(f"Error processing file {filename}: {e}", exc_info=True)
            return jsonify({"error": f"Failed to read or process the file: {e}"}), 500

    elif text_input:
        text_to_process = text_input
    
    if not text_to_process:
        return jsonify({"error": "No text provided from input or file."}), 400
        
    try:
        audio_file_path = process_text_to_speech(text_to_process)
        
        @app.after_request
        def remove_file(response):
            try:
                os.remove(audio_file_path)
                logging.info(f"Cleaned up temporary audio file: {audio_file_path}")
            except Exception as error:
                app.logger.error("Error removing or closing audio file: %s", error)
            return response
            
        return send_file(
            audio_file_path,
            mimetype='audio/wav',
            as_attachment=False
        )

    except Exception as e:
        logging.error(f"An error occurred during TTS processing: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- Main Entry Point ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)