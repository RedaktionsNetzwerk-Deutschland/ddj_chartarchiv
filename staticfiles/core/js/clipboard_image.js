document.addEventListener('DOMContentLoaded', function() {
    // Finde das versteckte Clipboard-Feld
    const clipboardField = document.querySelector('input[name="clipboard_image"]');
    
    if (clipboardField) {
        // Finde das Formular-Element
        const form = clipboardField.closest('form');
        
        // Finde das Vorschau-Element
        const previewContainer = document.querySelector('.field-display_thumbnail .readonly');
        
        // Füge eine Hilfe-Meldung hinzu
        const helpText = document.createElement('div');
        helpText.className = 'help';
        helpText.innerHTML = '<strong>Tipp:</strong> Du kannst ein Bild aus der Zwischenablage mit <strong>Strg+V</strong> direkt hier einfügen.';
        helpText.style.marginTop = '10px';
        
        // Füge die Hilfe nach dem Upload-Feld ein
        const uploadField = document.querySelector('.field-thumbnail');
        if (uploadField) {
            uploadField.appendChild(helpText);
        }
        
        // Event-Listener für Paste-Events im gesamten Formular
        form.addEventListener('paste', function(e) {
            // Überprüfe, ob Bilder in der Zwischenablage vorhanden sind
            const items = e.clipboardData.items;
            
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    // Verhindere das Standard-Einfügen
                    e.preventDefault();
                    
                    // Hole das Bild als Blob
                    const blob = items[i].getAsFile();
                    
                    // Erstelle einen FileReader, um das Bild als Data-URL zu lesen
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        // Speichere die Base64-Daten im versteckten Feld
                        clipboardField.value = event.target.result;
                        
                        // Aktualisiere die Vorschau
                        if (previewContainer) {
                            const previewHtml = `
                                <img src="${event.target.result}" style="max-height: 200px; max-width: 400px;" />
                                <br>Bildvorschau (noch nicht gespeichert)
                            `;
                            previewContainer.innerHTML = previewHtml;
                            
                            // Füge eine Meldung hinzu, dass das Formular gespeichert werden muss
                            const saveMessage = document.createElement('div');
                            saveMessage.className = 'help';
                            saveMessage.style.color = '#e74c3c';
                            saveMessage.style.fontWeight = 'bold';
                            saveMessage.textContent = 'Bitte auf "Speichern" klicken, um das Bild zu übernehmen!';
                            
                            // Entferne vorhandene Nachrichten und füge die neue hinzu
                            const existingMessages = document.querySelectorAll('.save-message');
                            existingMessages.forEach(msg => msg.remove());
                            
                            saveMessage.classList.add('save-message');
                            previewContainer.appendChild(saveMessage);
                        }
                    };
                    reader.readAsDataURL(blob);
                    break;
                }
            }
        });
    }
}); 