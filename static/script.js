let currentChapters = [];
let currentSessionId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing TTS Reader...');
    
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const textInput = document.getElementById('textInput');
    const processBtn = document.getElementById('processBtn');
    const generateAudioBtn = document.getElementById('generateAudioBtn');
    const resultsSection = document.getElementById('resultsSection');
    const chaptersPreview = document.getElementById('chaptersPreview');
    const generationProgress = document.getElementById('generationProgress');
    const downloadSection = document.getElementById('downloadSection');
    const downloadLink = document.getElementById('downloadLink');
    const filesList = document.getElementById('filesList');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');

    console.log('All elements found:', {
        fileInput: !!fileInput,
        processBtn: !!processBtn,
        textInput: !!textInput
    });

    // File input handler
    fileInput.addEventListener('change', function(e) {
        console.log('File input changed');
        const file = e.target.files[0];
        if (file) {
            console.log('File selected:', file.name, file.type, file.size);
            fileName.textContent = file.name;
            textInput.value = ''; // Clear text input when file is selected
        } else {
            fileName.textContent = '';
        }
    });

    // Text input handler
    textInput.addEventListener('input', function() {
        console.log('Text input changed, length:', this.value.length);
        if (this.value.trim()) {
            fileInput.value = ''; // Clear file input when text is entered
            fileName.textContent = '';
        }
    });

    // Process button handler
    processBtn.addEventListener('click', async function(e) {
        console.log('Process button clicked!');
        e.preventDefault();
        
        const file = fileInput.files[0];
        const text = textInput.value.trim();

        console.log('Processing with:', { 
            hasFile: !!file, 
            textLength: text.length,
            fileType: file ? file.type : 'none'
        });

        if (!file && !text) {
            console.log('No file or text provided');
            alert('Please select a file or enter text to process.');
            return;
        }

        // Show loading state
        processBtn.disabled = true;
        processBtn.querySelector('.btn-text').textContent = 'Processing...';
        processBtn.querySelector('.loading-spinner').style.display = 'inline';

        try {
            let response;
            
            if (file) {
                // Use FormData for file uploads
                console.log('Creating FormData for file upload...');
                const formData = new FormData();
                formData.append('file', file);
                if (text) {
                    formData.append('text_content', text);
                }
                
                console.log('Sending file upload request...');
                response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
            } else {
                // Use JSON for text-only requests
                console.log('Sending JSON request for text...');
                response = await fetch('/upload', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text_content: text
                    })
                });
            }

            console.log('Response status:', response.status);
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            console.log('Response content-type:', contentType);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.log('Error response text:', errorText);
                throw new Error(`Server error ${response.status}: ${errorText}`);
            }
            
            if (!contentType || !contentType.includes('application/json')) {
                const responseText = await response.text();
                console.log('Non-JSON response:', responseText);
                throw new Error(`Expected JSON but got: ${contentType}. Response: ${responseText.substring(0, 200)}`);
            }
            
            const result = await response.json();
            console.log('Response data:', result);

            if (result.success) {
                console.log('Processing successful, chapters:', result.chapters.length);
                currentChapters = result.chapters;
                displayChapters(result.chapters);
                resultsSection.style.display = 'block';
                generateAudioBtn.style.display = 'block';
                
                // Scroll to results
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                throw new Error(result.error || 'Failed to process document');
            }
        } catch (error) {
            console.error('Error processing document:', error);
            alert('Error processing document: ' + error.message);
        } finally {
            // Reset button state
            processBtn.disabled = false;
            processBtn.querySelector('.btn-text').textContent = 'Process Document';
            processBtn.querySelector('.loading-spinner').style.display = 'none';
        }
    });

    // Generate audio button handler
    generateAudioBtn.addEventListener('click', async function() {
        console.log('Generate audio button clicked');
        if (!currentChapters.length) {
            alert('No chapters to process.');
            return;
        }

        const voice = document.getElementById('voiceSelect').value;
        console.log('Selected voice:', voice);
        
        // Show progress section
        generationProgress.style.display = 'block';
        generateAudioBtn.style.display = 'none';
        downloadSection.style.display = 'none';
        
        // Reset progress
        progressBar.style.width = '0%';
        progressText.textContent = 'Starting audio generation...';

        try {
            console.log('Sending audio generation request...');
            const response = await fetch('/generate_audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    chapters: currentChapters,
                    voice: voice
                })
            });

            const result = await response.json();
            console.log('Audio generation response:', result);

            if (result.success) {
                currentSessionId = result.session_id;
                
                // Simulate progress (since we're not getting real-time updates)
                await simulateProgress(currentChapters.length);
                
                // Show download section
                displayDownloadSection(result.files, result.session_id);
                generationProgress.style.display = 'none';
                downloadSection.style.display = 'block';
                
                // Scroll to download section
                downloadSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                throw new Error(result.error || 'Failed to generate audio');
            }
        } catch (error) {
            console.error('Error generating audio:', error);
            alert('Error generating audio: ' + error.message);
            generationProgress.style.display = 'none';
            generateAudioBtn.style.display = 'block';
        }
    });

    async function simulateProgress(totalChapters) {
        const progressIncrement = 100 / totalChapters;
        let currentProgress = 0;

        for (let i = 0; i < totalChapters; i++) {
            await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay per chapter
            currentProgress += progressIncrement;
            progressBar.style.width = currentProgress + '%';
            progressText.textContent = `Processing chapter ${i + 1} of ${totalChapters}...`;
        }

        progressBar.style.width = '100%';
        progressText.textContent = 'Finalizing audio files...';
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    function displayChapters(chapters) {
        console.log('Displaying chapters:', chapters.length);
        chaptersPreview.innerHTML = '';
        
        chapters.forEach((chapter, index) => {
            const chapterDiv = document.createElement('div');
            chapterDiv.className = 'chapter-item';
            
            const titleDiv = document.createElement('div');
            titleDiv.className = 'chapter-title';
            titleDiv.textContent = `${index + 1}. ${chapter.title}`;
            
            const previewDiv = document.createElement('div');
            previewDiv.className = 'chapter-preview';
            const preview = chapter.content.length > 150 
                ? chapter.content.substring(0, 150) + '...' 
                : chapter.content;
            previewDiv.textContent = preview;
            
            chapterDiv.appendChild(titleDiv);
            chapterDiv.appendChild(previewDiv);
            chaptersPreview.appendChild(chapterDiv);
        });
    }

    function displayDownloadSection(files, sessionId) {
        console.log('Displaying download section:', files.length, 'files');
        downloadLink.href = `/download/${sessionId}`;
        
        filesList.innerHTML = '';
        
        files.forEach((file, index) => {
            const fileDiv = document.createElement('div');
            fileDiv.className = 'file-item';
            
            // File info container
            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info';
            
            const nameDiv = document.createElement('div');
            nameDiv.className = 'file-name';
            nameDiv.textContent = file.filename;
            
            fileInfo.appendChild(nameDiv);
            
            // Controls container
            const controlsDiv = document.createElement('div');
            controlsDiv.className = 'file-controls';
            
            // Add audio player for successful audio files
            if (file.status === 'success' && file.filename.match(/\.(wav|mp3)$/i)) {
                const audioContainer = document.createElement('div');
                audioContainer.className = 'audio-player';
                
                const audio = document.createElement('audio');
                audio.controls = true;
                audio.preload = 'none';
                audio.src = `/audio/${sessionId}/${file.filename}`;
                
                // Add error handling for audio
                audio.addEventListener('error', function() {
                    console.error('Error loading audio:', file.filename);
                    audioContainer.innerHTML = '<span style="color: #e53e3e; font-size: 0.8em;">Audio load failed</span>';
                });
                
                audioContainer.appendChild(audio);
                controlsDiv.appendChild(audioContainer);
                
                // Add a separate listen button for mobile/accessibility
                const listenBtn = document.createElement('button');
                listenBtn.className = 'listen-btn';
                listenBtn.innerHTML = '🔊 Listen';
                listenBtn.onclick = function() {
                    if (audio.paused) {
                        // Pause all other audio players first
                        document.querySelectorAll('audio').forEach(a => {
                            if (a !== audio) a.pause();
                        });
                        audio.play();
                        listenBtn.innerHTML = '⏸️ Pause';
                    } else {
                        audio.pause();
                        listenBtn.innerHTML = '🔊 Listen';
                    }
                };
                
                // Update button text when audio ends
                audio.addEventListener('ended', function() {
                    listenBtn.innerHTML = '🔊 Listen';
                });
                
                audio.addEventListener('pause', function() {
                    listenBtn.innerHTML = '🔊 Listen';
                });
                
                audio.addEventListener('play', function() {
                    listenBtn.innerHTML = '⏸️ Pause';
                });
                
                controlsDiv.appendChild(listenBtn);
            } else if (file.status === 'failed' || file.status === 'error') {
                // Show why audio generation failed
                const errorNote = document.createElement('span');
                errorNote.style.color = '#e53e3e';
                errorNote.style.fontSize = '0.8em';
                errorNote.textContent = file.status === 'failed' ? 'TTS generation failed' : 'Processing error';
                controlsDiv.appendChild(errorNote);
            }
            
            // Status indicator
            const statusSpan = document.createElement('span');
            statusSpan.className = `file-status status-${file.status}`;
            statusSpan.textContent = file.status.toUpperCase();
            controlsDiv.appendChild(statusSpan);
            
            fileDiv.appendChild(fileInfo);
            fileDiv.appendChild(controlsDiv);
            filesList.appendChild(fileDiv);
        });
    }
});