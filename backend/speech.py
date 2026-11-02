"""Voice questions only. Audio stays in memory and is sent to Groq after consent."""
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

router = APIRouter()
MAX_BYTES = 8 * 1024 * 1024
TYPES = {'audio/webm': 'webm', 'video/webm': 'webm', 'audio/ogg': 'ogg',
         'audio/mp4': 'm4a', 'video/mp4': 'm4a', 'audio/wav': 'wav',
         'audio/x-wav': 'wav'}


def transcribe(data, media_type, language):
    if not os.getenv('GROQ_API_KEY'):
        raise HTTPException(503, 'Clé Groq absente du backend / Groq key missing')
    try:
        from groq import Groq, GroqError
    except ImportError:
        raise HTTPException(503, 'Installe groq / Install groq') from None
    try:
        with Groq(timeout=45, max_retries=1) as client:
            response = client.audio.transcriptions.create(
                file=('question.' + TYPES[media_type], data, media_type),
                model=os.getenv('GROQ_STT_MODEL', 'whisper-large-v3-turbo'),
                language=language, response_format='json', temperature=0)
    except GroqError:
        raise HTTPException(502, 'Transcription indisponible. Réessaie ou écris ta question. / Transcription unavailable. Retry or type your question.') from None
    text = (response.text or '').strip()
    if not text:
        raise HTTPException(422, 'Aucune parole reconnue / No speech recognised')
    if len(text) > 1500:
        raise HTTPException(422, 'Question trop longue. Enregistre une question plus courte. / Question too long. Record a shorter question.')
    return {'text': text}


@router.post('/api/transcriptions')
async def voice_question(file: UploadFile = File(...), language: str = Form('fr'),
                         consent: bool = Form(False)):
    try:
        if not consent or language not in ('fr', 'en'):
            raise HTTPException(422, 'Consentement et langue requis / Consent and language required')
        media_type = (file.content_type or '').split(';')[0].lower()
        if media_type not in TYPES:
            raise HTTPException(415, 'Format vocal non pris en charge / Unsupported voice format')
        data = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, 'Audio vocal vide ou supérieur à 8 Mo / Voice audio empty or above 8 MB')
    return await run_in_threadpool(transcribe, data, media_type, language)
