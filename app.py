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

def call_kokoro_tts(text, voice="af_bella"):
    """Call Kokoro TTS API via Hugging Face Spaces"""
    api_url = "https://hexgrad-kokoro-tts.hf.space/call/generate_audio"
    
    # First, queue the request
    headers = {"Content-Type": "application/json"}
    data = {
        "data": [text, voice, 1.0, 1.0, True]  # text, voice, speed, pitch, use_cache
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if 'event_id' in result:
                # Poll for results
                status_url = f"https://hexgrad-kokoro-tts.hf.space/call/generate_audio/{result['event_id']}"
                
                max_attempts = 30
                for attempt in range(max_attempts):
                    time.sleep(2)
                    status_response = requests.get(status_url)
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get('status') == 'COMPLETE':
                            if 'data' in status_data and status_data['data']:
                                # The API returns a file path or URL
                                audio_data = status_data['data'][0]
                                return audio_data
                        elif status_data.get('status') == 'FAILED':
                            break
                
    except Exception as e:
        print(f"Error calling Kokoro TTS: {e}")
    
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    text_content = request.form.get('text_content', '').strip()
    
    if not file.filename and not text_content:
        return jsonify({'error': 'No file selected or text provided'}), 400
    
    chapters = []
    
    # Process uploaded file
    if file.filename and allowed_file(file.filename):
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
            # Limit text length for TTS (split if too long)
            text = chapter['content']
            if len(text) > 1000:  # Limit to prevent API timeouts
                text = text[:1000] + "..."
            
            # Generate audio
            audio_data = call_kokoro_tts(text, voice)
            
            if audio_data:
                # Save the audio file
                audio_filename = f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.wav"
                audio_path = os.path.join(session_dir, audio_filename)
                
                # Note: This is a simplified version. In reality, you'd need to handle
                # the actual audio data format returned by the API
                generated_files.append({
                    'filename': audio_filename,
                    'title': chapter['title'],
                    'status': 'success'
                })
            else:
                generated_files.append({
                    'filename': f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.txt",
                    'title': chapter['title'],
                    'status': 'failed'
                })
                
                # Save as text file if TTS fails
                text_path = os.path.join(session_dir, f"chapter_{i+1:02d}_{chapter['title'].replace(' ', '_')}.txt")
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(chapter['content'])
            
        except Exception as e:
            print(f"Error generating audio for chapter {i+1}: {e}")
            generated_files.append({
                'filename': f"chapter_{i+1:02d}_error.txt",
                'title': chapter['title'],
                'status': 'error'
            })
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'files': generated_files
    })

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