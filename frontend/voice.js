'use strict';
(() => {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  if (!form || !input) return;
  const english = document.documentElement.lang === 'en';
  const tr = (fr, en) => english ? en : fr;
  const mic = document.createElement('button');
  mic.type = 'button'; mic.className = 'voice-button';
  const cancel = document.createElement('button');
  cancel.type = 'button'; cancel.textContent = tr('Annuler', 'Cancel'); cancel.hidden = true;
  const status = document.createElement('p');
  status.className = 'chat-disclaimer'; status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  form.append(mic, cancel); form.after(status);
  let recorder, stream, timer, parts = [], pending = false, discarded = false, active = false;
  const label = () => {mic.textContent = tr('Micro', 'Mic'); mic.setAttribute('aria-label', tr('Dicter une question', 'Dictate a question')); mic.setAttribute('aria-pressed', 'false');};
  label();
  const release = () => {clearTimeout(timer); stream?.getTracks().forEach(track => track.stop()); stream = null;};
  const finish = () => {release(); active = false; pending = false; mic.disabled = false; cancel.hidden = true; input.readOnly = false; label();};
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    mic.disabled = true; mic.title = tr('Micro indisponible. Utilise Chrome sur localhost ou HTTPS.', 'Microphone unavailable. Use Chrome on localhost or HTTPS.');
    return;
  }
  form.addEventListener('submit', event => {
    if (active || pending) {event.preventDefault(); event.stopImmediatePropagation();}
  }, true);
  cancel.onclick = () => {
    discarded = true;
    if (recorder?.state === 'recording') recorder.stop();
    release(); status.textContent = tr('Enregistrement annulé.', 'Recording cancelled.');
  };
  mic.onclick = async () => {
    if (recorder?.state === 'recording') {recorder.stop(); return;}
    if (pending || active) return;
    if (!confirm(tr('Ta question vocale sera envoyée à Groq pour transcription. Tu pourras corriger le texte avant de l’envoyer au chat. Continuer ?', 'Your voice question will be sent to Groq for transcription. You can edit the text before sending it to chat. Continue?'))) return;
    pending = true; mic.disabled = true; discarded = false; parts = [];
    const analysisId = typeof current === 'undefined' ? null : current?.id;
    status.textContent = tr('Autorise l’accès au micro…', 'Allow microphone access…');
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: true});
      if (discarded) {finish(); return;}
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type));
      if (!mime) throw Error(tr('Format du navigateur non pris en charge. Utilise Chrome.', 'Browser recording format unsupported. Use Chrome.'));
      recorder = new MediaRecorder(stream, {mimeType: mime});
      recorder.ondataavailable = event => {if (event.data.size) parts.push(event.data);};
      recorder.onerror = () => {discarded = true; status.textContent = tr('Échec du micro. Réessaie ou écris ta question.', 'Microphone failed. Retry or type your question.'); if (recorder.state === 'recording') recorder.stop(); finish();};
      recorder.onstop = async () => {
        release(); mic.disabled = true; cancel.hidden = true; active = false; pending = true;
        try {
          if (discarded) return;
          const blob = new Blob(parts, {type: mime}); parts = [];
          if (!blob.size || blob.size > 8 * 1024 * 1024) throw Error(tr('Audio vide ou trop volumineux. Réessaie.', 'Audio empty or too large. Retry.'));
          status.textContent = tr('Transcription en cours…', 'Transcribing…');
          const data = new FormData();
          data.append('file', blob, mime.includes('mp4') ? 'question.m4a' : mime.includes('ogg') ? 'question.ogg' : 'question.webm');
          data.append('language', english ? 'en' : 'fr'); data.append('consent', 'true');
          const response = await fetch('/api/transcriptions', {method: 'POST', body: data});
          const result = await response.json();
          if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : tr('Échec de transcription.', 'Transcription failed.'));
          if (discarded) return;
          if ((typeof current === 'undefined' ? null : current?.id) !== analysisId) throw Error(tr('L’analyse a changé. Enregistre ta question à nouveau.', 'The analysis changed. Record your question again.'));
          const combined = [input.value.trim(), result.text].filter(Boolean).join(' ');
          if (combined.length > input.maxLength) throw Error(tr('Le texte dépasse la limite. Raccourcis ta question puis réessaie.', 'Text exceeds the limit. Shorten your question and retry.'));
          input.value = combined; input.dispatchEvent(new Event('input', {bubbles: true})); input.focus();
          status.textContent = tr('Vérifie le texte, puis clique sur Envoyer. La transcription peut contenir des erreurs.', 'Review the text, then click Send. Transcription can contain errors.');
        } catch (error) {status.textContent = error.message;}
        finally {parts = []; finish();}
      };
      active = true; pending = false; mic.disabled = false; cancel.hidden = false; input.readOnly = true;
      mic.textContent = tr('Arrêter', 'Stop'); mic.setAttribute('aria-pressed', 'true');
      mic.setAttribute('aria-label', tr('Arrêter et transcrire', 'Stop and transcribe'));
      recorder.start(); status.textContent = tr('Parle, puis clique sur Arrêter. Maximum 60 secondes.', 'Speak, then click Stop. Maximum 60 seconds.');
      timer = setTimeout(() => {if (recorder.state === 'recording') recorder.stop();}, 60000);
    } catch (error) {finish(); status.textContent = error.name === 'NotAllowedError' ? tr('Accès au micro refusé. Autorise-le dans ton navigateur ou écris ta question.', 'Microphone permission denied. Allow it in your browser or type your question.') : error.message;}
  };
  window.addEventListener('pagehide', () => {discarded = true; if (recorder?.state === 'recording') recorder.stop(); release();});
})();
