from flask import Flask, render_template, request, jsonify, send_file
import os
import re
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import json
import time
from werkzeug.utils import secure_filename
import zipfile
from io import BytesIO

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'epub'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF and split into chapters"""
    chapters = []
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        current_chapter = ""
        chapter_count = 1
        
        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            
            # Simple chapter detection (you can improve this)
            chapter_markers = re.findall(r'Chapter\s+\d+|CHAPTER\s+\d+|Chapter\s+[IVX]+', text, re.IGNORECASE)
            
            if chapter_markers and current_chapter and page_num > 0:
                chapters.append({
                    'title': f'Chapter {chapter_count}',
                    'content': current_chapter.strip()
                })
                current_chapter = text
                chapter_count += 1
            else:
                current_chapter += "\n" + text
        
        # Add the last chapter
        if current_chapter.strip():
            chapters.append({
                'title': f'Chapter {chapter_count}',
                'content': current_chapter.strip()
            })
    
    return chapters

def extract_text_from_epub(file_path):
    """Extract text from EPUB and split into chapters"""
    chapters = []
    book = epub.read_epub(file_path)
    
    chapter_count = 1
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            
            if text.strip():
                # Try to get title from the item
                title = item.get_name() or f'Chapter {chapter_count}'
                chapters.append({
                    'title': title,
                    'content': text.strip()
                })
                chapter_count += 1
    
    return chapters

def extract_text_from_txt(file_path):
    """Extract text from TXT file and split into chapters"""
    chapters = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Simple chapter splitting based on common patterns
    chapter_splits = re.split(r'\n\s*(?:Chapter\s+\d+|CHAPTER\s+\d+|Chapter\s+[IVX]+).*?\n', content, flags=re.IGNORECASE)
    
    if len(chapter_splits) <= 1:
        # If no chapters found, split by large text blocks
        paragraphs = content.split('\n\n')
        chunk_size = max(1, len(paragraphs) // 10)  # Aim for ~10 chunks
        
        for i in range(0, len(paragraphs), chunk_size):
            chunk = '\n\n'.join(paragraphs[i:i+chunk_size])
            if chunk.strip():
                chapters.append({
                    'title': f'Section {len(chapters) + 1}',
                    'content': chunk.strip()
                })
    else:
        for i, chapter_text in enumerate(chapter_splits):
            if chapter_text.strip():
                chapters.append({
                    'title': f'Chapter {i + 1}',
                    'content': chapter_text.strip()
                })
    
    return chapters

from flask import Flask, render_template, request, jsonify, send_file
import os
import re
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import time
from werkzeug.utils import secure_filename
import zipfile
from io import BytesIO
import tempfile
import subprocess

def call_kokoro_tts(text, voice="af_bella"):
    """Generate TTS using multiple local TTS engines"""
    print(f"Generating TTS for text length: {len(text)} with voice: {voice}")
    
    # Limit text length
    if len(text) > 1000:
        text = text[:1000] + "..."
    
    # Try Edge TTS first (Microsoft's high-quality TTS)
    try:
        print("Attempting Edge TTS...")
        import asyncio
        import edge_tts
        import tempfile
        
        # Voice mapping for Edge TTS
        edge_voices = {
            "af_bella": "en-US-AriaNeural",      # Female US
            "af_sarah": "en-US-JennyNeural",     # Female US
            "am_adam": "en-US-GuyNeural",        # Male US
            "am_michael": "en-US-DavisNeural",   # Male US
            "bf_emma": "en-GB-LibbyNeural",      # Female UK
            "bm_lewis": "en-GB-RyanNeural"       # Male UK
        }
        
        edge_voice = edge_voices.get(voice, "en-US-AriaNeural")
        
        async def generate_edge_tts():
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            communicate = edge_tts.Communicate(text, edge_voice)
            await communicate.save(temp_path)
            
            if os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    audio_data = f.read()
                os.unlink(temp_path)
                return audio_data
            return None
        
        # Run the async function
        audio_data = asyncio.run(generate_edge_tts())
        
        if audio_data:
            print("Edge TTS generation successful!")
            return audio_data
            
    except Exception as e:
        print(f"Error with Edge TTS: {e}")
    
    # Try Google TTS as fallback
    try:
        print("Attempting Google TTS (gTTS)...")
        from gtts import gTTS
        import tempfile
        
        # Language mapping
        lang_mapping = {
            "af_bella": "en",
            "af_sarah": "en", 
            "am_adam": "en",
            "am_michael": "en",
            "bf_emma": "en",
            "bm_lewis": "en"
        }
        
        lang = lang_mapping.get(voice, "en")
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_path)
        
        # Convert MP3 to WAV using ffmpeg
        wav_path = temp_path.replace('.mp3', '.wav')
        subprocess.run([
            'ffmpeg', '-i', temp_path, '-ar', '22050', '-ac', '1', wav_path, '-y'
        ], capture_output=True, check=True)
        
        if os.path.exists(wav_path):
            with open(wav_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up temp files
            os.unlink(temp_path)
            os.unlink(wav_path)
            
            print("Google TTS generation successful!")
            return audio_data
            
    except Exception as e:
        print(f"Error with Google TTS: {e}")
    
    # Final fallback to espeak
    try:
        print("Using espeak as final fallback...")
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        # Voice mapping for espeak
        espeak_voices = {
            "af_bella": "en+f3",
            "af_sarah": "en+f4", 
            "am_adam": "en+m1",
            "am_michael": "en+m2",
            "bf_emma": "en-gb+f3",
            "bm_lewis": "en-gb+m1"
        }
        
        espeak_voice = espeak_voices.get(voice, "en+f3")
        
        cmd = [
            'espeak-ng', 
            '-v', espeak_voice,
            '-s', '150',        # Speed
            '-a', '100',        # Amplitude
            '-w', temp_path,    # Output file
            text
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and os.path.exists(temp_path):
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            os.unlink(temp_path)
            print("Espeak TTS successful!")
            return audio_data
        else:
            print(f"Espeak failed: {result.stderr}")
            
    except Exception as e:
        print(f"Error with espeak: {e}")
    
    print("All TTS methods failed")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("=== Upload request received ===")
    print("Content-Type:", request.content_type)
    print("Request files:", request.files.keys())
    print("Request form:", request.form.keys())
    
    # Handle JSON requests (text-only)
    if request.content_type == 'application/json':
        data = request.get_json()
        print("JSON data:", data)
        text_content = data.get('text_content', '').strip()
        file = None
    else:
        # Handle form data requests (file uploads)
        file = request.files.get('file')
        text_content = request.form.get('text_content', '').strip()
    
    print(f"File: {file}")
    print(f"File filename: {file.filename if file else 'No file'}")
    print(f"Text content length: {len(text_content)}")
    print(f"Text content preview: {text_content[:100] if text_content else 'No text'}")
    
    if not file or not file.filename:
        if not text_content:
            print("ERROR: No file and no text content")
            return jsonify({'error': 'No file selected or text provided'}), 400
        else:
            print("No file, but text content found - proceeding with text")
    
    if file and file.filename and not allowed_file(file.filename):
        print(f"ERROR: File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    
    chapters = []
    
    # Process uploaded file
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            if filename.lower().endswith('.pdf'):
                chapters = extract_text_from_pdf(file_path)
            elif filename.lower().endswith('.epub'):
                chapters = extract_text_from_epub(file_path)
            elif filename.lower().endswith('.txt'):
                chapters = extract_text_from_txt(file_path)
            
            # Clean up uploaded file
            os.remove(file_path)
            
        except Exception as e:
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
    
    # Process text content
    elif text_content:
        chapters = [{
            'title': 'Text Input',
            'content': text_content
        }]
    
    if not chapters:
        return jsonify({'error': 'No content found to process'}), 400
    
    return jsonify({
        'success': True,
        'chapters': chapters,
        'total_chapters': len(chapters)
    })

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    data = request.get_json()
    chapters = data.get('chapters', [])
    voice = data.get('voice', 'af_bella')
    
    if not chapters:
        return jsonify({'error': 'No chapters provided'}), 400
    
    # Create output directory for this session
    session_id = str(int(time.time()))
    session_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    generated_files = []
    
    for i, chapter in enumerate(chapters):
        try:
            print(f"Processing chapter {i+1}/{len(chapters)}: {chapter['title']}")
            
            # Limit text length for TTS (split if too long)
            text = chapter['content']
            if len(text) > 1000:  # Limit to prevent API timeouts
                text = text[:1000] + "..."
                print(f"Text truncated to 1000 characters")
            
            # Generate audio
            audio_data = call_kokoro_tts(text, voice)
            
            if audio_data:
                # Save the audio file
                audio_filename = f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.wav"
                audio_path = os.path.join(session_dir, audio_filename)
                
                try:
                    # Handle different types of audio data
                    if isinstance(audio_data, bytes):
                        # Direct binary audio data
                        with open(audio_path, 'wb') as f:
                            f.write(audio_data)
                        print(f"Saved binary audio: {audio_filename}")
                    elif isinstance(audio_data, str):
                        if audio_data.startswith('data:audio'):
                            # Base64 encoded audio data
                            import base64
                            header, encoded = audio_data.split(',', 1)
                            audio_bytes = base64.b64decode(encoded)
                            with open(audio_path, 'wb') as f:
                                f.write(audio_bytes)
                            print(f"Saved base64 audio: {audio_filename}")
                        elif audio_data.startswith('http'):
                            # URL to audio file
                            audio_response = requests.get(audio_data, timeout=30)
                            if audio_response.status_code == 200:
                                with open(audio_path, 'wb') as f:
                                    f.write(audio_response.content)
                                print(f"Downloaded and saved audio: {audio_filename}")
                            else:
                                raise Exception(f"Failed to download audio from URL: {audio_data}")
                        else:
                            # Assume it's a file path or some other string
                            print(f"Unexpected audio data format: {type(audio_data)} - {str(audio_data)[:100]}")
                            raise Exception("Unsupported audio data format")
                    else:
                        print(f"Unexpected audio data type: {type(audio_data)}")
                        raise Exception("Unsupported audio data type")
                    
                    generated_files.append({
                        'filename': audio_filename,
                        'title': chapter['title'],
                        'status': 'success'
                    })
                    
                except Exception as save_error:
                    print(f"Error saving audio file: {save_error}")
                    # Fall back to text file
                    text_filename = f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.txt"
                    text_path = os.path.join(session_dir, text_filename)
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(chapter['content'])
                    
                    generated_files.append({
                        'filename': text_filename,
                        'title': chapter['title'],
                        'status': 'failed'
                    })
            else:
                print(f"TTS failed for chapter {i+1}")
                # Save as text file if TTS fails
                text_filename = f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.txt"
                text_path = os.path.join(session_dir, text_filename)
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(chapter['content'])
                
                generated_files.append({
                    'filename': text_filename,
                    'title': chapter['title'],
                    'status': 'failed'
                })
            
        except Exception as e:
            print(f"Error generating audio for chapter {i+1}: {e}")
            # Save as text file on any error
            text_filename = f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}_error.txt"
            text_path = os.path.join(session_dir, text_filename)
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(f"Error processing chapter: {str(e)}\n\nOriginal content:\n{chapter['content']}")
            
            generated_files.append({
                'filename': text_filename,
                'title': chapter['title'],
                'status': 'error'
            })
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'files': generated_files
    })

@app.route('/audio/<session_id>/<filename>')
def serve_audio(session_id, filename):
    """Serve audio files for preview"""
    try:
        session_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        file_path = os.path.join(session_dir, filename)
        
        if os.path.exists(file_path) and filename.endswith(('.wav', '.mp3')):
            return send_file(file_path, mimetype='audio/wav' if filename.endswith('.wav') else 'audio/mpeg')
        else:
            return "Audio file not found", 404
    except Exception as e:
        return f"Error serving audio: {str(e)}", 500

@app.route('/download/<session_id>')
def download_files(session_id):
    session_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
    
    if not os.path.exists(session_dir):
        return "Session not found", 404
    
    # Create a ZIP file with all generated files
    memory_file = BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(session_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, session_dir)
                zf.write(file_path, arc_name)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'tts_output_{session_id}.zip'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2022, debug=True)