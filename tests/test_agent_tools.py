"""S2 contracts, trusted registration, citation checks and human-approved writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from machineear.agent_tools.executor import ToolExecutor
from machineear.agent_tools.schemas import tool_schemas
from machineear.agent_tools.models import SearchManualsOutput


def audio_result():
    return {'machine_type': 'fan', 'machine_id': 'id_00', 'model': 'logmel_knn5_mean',
            'anomaly_score': .75, 'threshold': .7, 'is_anomaly': True, 'duration_seconds': 2.,
            'n_windows': 1, 'windows': [{'start_seconds': 0., 'end_seconds': 2., 'score': .75}]}


def record():
    return {'id': 'original-record', 'created_at': '2026-11-04T00:00:00+00:00',
            'analysis': {'audio': audio_result(), 'retrieval': {'results': []}}}


def passage():
    return {'chunk_id': 'chunk-1', 'text': 'Inspect lubrication.', 'source_relative_path': 'Fan_Docs/manual.pdf',
            'pdf_page_number': 3, 'citation': '[manual.pdf, PDF p. 3]', 'semantic_similarity': .9,
            'citation_verified': True, 'machine_scope': 'fan', 'needs_review': False}


class AgentToolTests(unittest.TestCase):
    def test_exported_schemas_match_code_and_have_three_classified_tools(self):
        from machineear.paths import ROOT
        data = tool_schemas()
        self.assertEqual(json.loads((ROOT/'schemas/machineear_tools.json').read_text()), data)
        self.assertEqual([x['access'] for x in data], ['read', 'read', 'write'])
        for item in data:
            self.assertFalse(item['tool']['function']['parameters']['additionalProperties'])
            self.assertTrue(item['output_schema'])

    def test_audio_delegation_preserves_scores_and_validates_before_call(self):
        predictor = Mock(return_value=audio_result())
        executor = ToolExecutor(predictor=predictor)
        key = executor.register_recording(b'fixture, not real WAV audio')
        args = {'recording_id': key, 'machine_type': 'fan', 'machine_id': 'id_00'}
        result = executor.execute('analyze_audio', json.dumps(args))
        self.assertEqual(result['anomaly_score'], .75)
        self.assertEqual(result['windows'], audio_result()['windows'])
        predictor.assert_called_once_with(b'fixture, not real WAV audio', machine_type='fan', machine_id='id_00')
        for bad in ({**args, 'machine_type': 'motor'}, {**args, 'model_dir': '/tmp'},
                    {**args, 'machine_id': '../id_00'}):
            with self.assertRaises(ValidationError):
                executor.execute('analyze_audio', bad)
        self.assertEqual(predictor.call_count, 1)
        with self.assertRaises(ValueError):
            executor.execute('analyze_audio', {**args, 'recording_id': '/etc/passwd'})

    def test_bad_audio_output_is_rejected(self):
        predictor = Mock(return_value={**audio_result(), 'is_anomaly': False})
        executor = ToolExecutor(predictor=predictor)
        key = executor.register_recording(b'fixture')
        args = {'recording_id': key, 'machine_type': 'fan', 'machine_id': 'id_00'}
        with self.assertRaises(ValidationError):
            executor.execute('analyze_audio', args)
        predictor.return_value = {**audio_result(), 'anomaly_score': float('nan')}
        with self.assertRaises(ValidationError):
            executor.execute('analyze_audio', args)

    def test_search_routes_parameters_and_rejects_bad_evidence(self):
        retriever = Mock()
        retriever.search.return_value = {'status': 'passages_for_review', 'results': [passage()]}
        executor = ToolExecutor(retriever=retriever)
        args = {'query': 'bearing grease', 'machine_type': 'fan', 'language': 'en', 'top_k': 5}
        result = executor.execute('search_manuals', args)
        self.assertEqual(result['passages'][0]['pdf_page_number'], 3)
        retriever.search.assert_called_once_with('bearing grease', 'fan', language='en', top_k=5)
        for changes in ({'citation_verified': False}, {'machine_scope': 'pump'}, {'needs_review': True}):
            retriever.search.return_value = {'status': 'passages_for_review', 'results': [{**passage(), **changes}]}
            with self.assertRaises(ValueError):
                executor.execute('search_manuals', args)
        for bad in ({**args, 'query': '   '}, {**args, 'top_k': '5'}, {**args, 'top_k': 6}):
            with self.assertRaises(ValidationError):
                executor.execute('search_manuals', bad)

    def test_search_empty_status_and_upstream_failures(self):
        retriever = Mock()
        executor = ToolExecutor(retriever=retriever)
        args = {'query': 'cake', 'machine_type': 'fan', 'language': 'en', 'top_k': 1}
        retriever.search.return_value = {'status': 'no_supported_passages', 'results': []}
        self.assertEqual(executor.execute('search_manuals', args)['passages'], [])
        with self.assertRaises(ValidationError):
            SearchManualsOutput(status='passages_for_review', passages=[])
        retriever.search.side_effect = RuntimeError('missing local model')
        with self.assertRaisesRegex(RuntimeError, 'missing local model'):
            executor.execute('search_manuals', args)

    def test_save_requires_bound_approval_preserves_history_and_prevents_replay(self):
        from machineear.review import load_history
        with tempfile.TemporaryDirectory() as folder:
            executor = ToolExecutor(history_dir=folder)
            original = record()
            key = executor.register_report(original)
            original['analysis']['audio']['threshold'] = 100  # registered snapshot must be independent
            args = {'report_id': key, 'reviewed_text': '  Reviewed report.\n', 'approval_id': 'invented'}
            with self.assertRaises(PermissionError):
                executor.execute('save_report_revision', args)
            self.assertEqual(list(Path(folder).glob('*.json')), [])
            approval = executor.approve_report(key, args['reviewed_text'], 'Human reviewer', applicability_checked=True)
            args['approval_id'] = approval
            other = executor.register_report(record())
            for bad in ({**args, 'reviewed_text': 'Changed report.'}, {**args, 'report_id': other}):
                with self.assertRaises(PermissionError):
                    executor.execute('save_report_revision', bad)
            for bad in ({**args, 'approved': True}, {**args, 'directory': '/tmp'}):
                with self.assertRaises(ValidationError):
                    executor.execute('save_report_revision', bad)
            output = executor.execute('save_report_revision', args)
            rows, errors = load_history(folder)
            self.assertEqual(errors, [])
            self.assertEqual(rows[0]['review']['report'], args['reviewed_text'])
            self.assertEqual(rows[0]['agent_revision_id'], output['revision_id'])
            self.assertEqual(rows[0]['analysis']['audio']['threshold'], .7)
            with self.assertRaises(PermissionError):
                executor.execute('save_report_revision', args)
            approval2 = executor.approve_report(key, 'Second revision.', 'Human reviewer', applicability_checked=True)
            executor.execute('save_report_revision', {**args, 'reviewed_text': 'Second revision.', 'approval_id': approval2})
            self.assertEqual(len(list(Path(folder).glob('*.json'))), 2)

    def test_failed_save_does_not_consume_approval(self):
        executor = ToolExecutor()
        key = executor.register_report(record())
        for reviewer, checked in (('', True), ('Human', False), ('Human', 'true')):
            with self.assertRaises(PermissionError):
                executor.approve_report(key, 'text', reviewer, applicability_checked=checked)
        token = executor.approve_report(key, 'text', 'Human', applicability_checked=True)
        with patch('machineear.review.save_review', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                executor.execute('save_report_revision', {'report_id': key, 'reviewed_text': 'text', 'approval_id': token})
        self.assertIn(token, executor._approvals)
        with self.assertRaises(ValueError):
            executor.execute('approve_report', {})

    def test_import_starts_no_worker_or_model(self):
        import subprocess, sys
        result = subprocess.run([sys.executable, '-B', '-c',
            "import sys; import machineear.agent_tools.executor; "
            "assert not {'numpy','pymupdf','machineear.audio_bridge'}.intersection(sys.modules)"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
