let currentChapters = [];
let currentSessionId = null;

document.addEventListener('DOMContentLoaded', function() {
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

    // File input handler
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            fileName.textContent = file.name;
            textInput.value = ''; // Clear text input when file is selected
        } else {
            fileName.textContent = '';
        }
    });

    // Text input handler
    textInput.addEventListener('input', function() {
        if (this.value.trim()) {
            fileInput.value = ''; // Clear file input when text is entered
            fileName.textContent = '';
        }
    });

    // Process button handler
    processBtn.addEventListener('click', async function() {
        const file = fileInput.files[0];
        const text = textInput.value.trim();

        if (!file && !text) {
            alert('Please select a file or enter text to process.');
            return;
        }

        // Show loading state
        processBtn.disabled = true;
        processBtn.querySelector('.btn-text').textContent = 'Processing...';
        processBtn.querySelector('.loading-spinner').style.display = 'inline';

        try {
            const formData = new FormData();
            if (file) {
                formData.append('file', file);
            }
            if (text) {
                formData.append('text_content', text);
            }

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
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
        if (!currentChapters.length) {
            alert('No chapters to process.');
            return;
        }

        const voice = document.getElementById('voiceSelect
