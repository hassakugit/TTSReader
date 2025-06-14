// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('tts-form');
    const submitButton = document.getElementById('submit-button');
    const resultsDiv = document.getElementById('results');
    const loadingSpinner = document.getElementById('loading-spinner');
    const audioOutputDiv = document.getElementById('audio-output');
    const textInput = document.getElementById('text-input');
    const fileInput = document.getElementById('file-input');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData();
        const textValue = textInput.value.trim();
        const fileValue = fileInput.files[0];

        if (!textValue && !fileValue) {
            alert('Please enter some text or upload a file.');
            return;
        }

        // Add form data
        formData.append('text_input', textValue);
        if (fileValue) {
            formData.append('file_input', fileValue);
        }

        // --- UI updates for loading state ---
        submitButton.disabled = true;
        submitButton.textContent = 'Generating...';
        resultsDiv.classList.remove('hidden');
        loadingSpinner.style.display = 'block';
        audioOutputDiv.innerHTML = ''; // Clear previous results

        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'An unknown error occurred.');
            }

            const blob = await response.blob();
            const audioUrl = URL.createObjectURL(blob);
            
            // Create audio player
            const audioPlayer = document.createElement('audio');
            audioPlayer.controls = true;
            audioPlayer.src = audioUrl;

            // Create download link
            const downloadLink = document.createElement('a');
            downloadLink.href = audioUrl;
            downloadLink.download = 'tts_output.wav';
            downloadLink.textContent = 'Download Audio File';
            downloadLink.classList.add('download-link');

            // Append to the page
            audioOutputDiv.appendChild(audioPlayer);
            audioOutputDiv.appendChild(downloadLink);

        } catch (error) {
            audioOutputDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            console.error('Error during TTS processing:', error);
        } finally {
            // --- UI updates to restore state ---
            submitButton.disabled = false;
            submitButton.textContent = 'Generate Speech';
            loadingSpinner.style.display = 'none';
        }
    });
});
