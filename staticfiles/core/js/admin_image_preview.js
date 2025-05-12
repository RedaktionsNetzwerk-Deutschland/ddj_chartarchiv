document.addEventListener('DOMContentLoaded', function() {
    // Finde das Bild-Upload-Feld
    const imageField = document.querySelector('input[type="file"][name="background_image"]');
    
    if (imageField) {
        // Finde das Vorschau-Element
        const previewContainer = document.querySelector('.field-image_preview .readonly');
        
        if (previewContainer) {
            // Event-Listener für Dateiauswahl hinzufügen
            imageField.addEventListener('change', function() {
                const file = this.files[0];
                
                if (file && file.type.match('image.*')) {
                    // Erstelle einen URL für das hochgeladene Bild
                    const imageUrl = URL.createObjectURL(file);
                    
                    // Erstelle ein neues Vorschau-Element
                    const previewHtml = `
                        <img src="${imageUrl}" style="max-height: 200px; max-width: 400px;" />
                        <br>Bildvorschau (noch nicht gespeichert)
                    `;
                    
                    // Aktualisiere die Vorschau
                    previewContainer.innerHTML = previewHtml;
                    
                    // Füge eine Meldung hinzu, dass das Formular gespeichert werden muss
                    const saveMessage = document.createElement('div');
                    saveMessage.className = 'help';
                    saveMessage.style.color = '#e74c3c';
                    saveMessage.style.fontWeight = 'bold';
                    saveMessage.textContent = 'Bitte auf "Speichern" klicken, um das Bild zu übernehmen!';
                    
                    // Füge die Meldung nach dem Upload-Feld ein
                    const fieldBox = imageField.closest('.form-row');
                    if (fieldBox && !fieldBox.querySelector('.save-message')) {
                        saveMessage.classList.add('save-message');
                        fieldBox.appendChild(saveMessage);
                    }
                }
            });
        }
    }
}); 