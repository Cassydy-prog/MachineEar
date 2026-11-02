"""Voice route tests use mocked transcription and never send audio externally."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.speech import router, MAX_BYTES


class VoiceTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def post(self, **fields):
        return self.client.post('/api/transcriptions',
            data={'consent': 'true', 'language': 'fr', **fields},
            files={'file': ('question.webm', b'fixture', 'audio/webm')})

    @patch('backend.speech.transcribe', return_value={'text': 'Quels contrôles ?'})
    def test_transcript_returned_without_chat_submission(self, transcribe):
        result = self.post()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {'text': 'Quels contrôles ?'})
        transcribe.assert_called_once_with(b'fixture', 'audio/webm', 'fr')

    @patch('backend.speech.transcribe')
    def test_missing_consent_and_invalid_language_rejected(self, transcribe):
        self.assertEqual(self.post(consent='false').status_code, 422)
        self.assertEqual(self.post(language='xx').status_code, 422)
        transcribe.assert_not_called()

    @patch('backend.speech.transcribe')
    def test_unsupported_and_empty_upload_rejected(self, transcribe):
        for data, mime, code in [(b'fixture', 'text/plain', 415), (b'', 'audio/webm', 413)]:
            result = self.client.post('/api/transcriptions', data={'consent': 'true'},
                files={'file': ('question', data, mime)})
            self.assertEqual(result.status_code, code)
        transcribe.assert_not_called()

    @patch('backend.speech.transcribe')
    def test_oversized_upload_rejected(self, transcribe):
        result = self.client.post('/api/transcriptions', data={'consent': 'true'},
            files={'file': ('question.webm', b'x' * (MAX_BYTES + 1), 'audio/webm')})
        self.assertEqual(result.status_code, 413)
        transcribe.assert_not_called()

    @patch.dict('os.environ', {'GROQ_API_KEY': ''})
    def test_missing_key_reported(self):
        self.assertEqual(self.post().status_code, 503)


if __name__ == '__main__':
    unittest.main()
