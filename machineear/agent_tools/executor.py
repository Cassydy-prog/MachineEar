"""Local validated dispatcher. Registration and approval are trusted host actions."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from machineear.agent_tools.models import (
    AnalyzeAudioOutput, SearchManualsOutput, SaveReportRevisionOutput,
)
from machineear.agent_tools.schemas import TOOLS


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ToolExecutor:
    """One user's local session. Never expose host methods as model tools.

    This is an in-process approval gate, not a multi-user authentication system.
    A future server must authenticate humans and isolate executors per session.
    """
    def __init__(self, *, history_dir=None, retriever=None, predictor=None):
        self.history_dir = Path(history_dir) if history_dir is not None else None
        self.retriever, self.predictor = retriever, predictor
        self._recordings, self._records, self._approvals = {}, {}, {}

    def register_recording(self, source):
        """Trusted host: register upload bytes or a file chosen by the user."""
        if isinstance(source, (bytes, bytearray)):
            if not source:
                raise ValueError('Recording cannot be empty')
            source = bytes(source)
        else:
            source = Path(source).expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.lower() != '.wav':
                raise ValueError('Select a WAV file')
        key = uuid4().hex
        self._recordings[key] = source
        return key

    def register_report(self, record):
        """Trusted host: register an existing review.new_record() result."""
        required = ('id', 'created_at', 'analysis')
        if not isinstance(record, dict) or any(k not in record for k in required):
            raise ValueError('Expected a review record with id, created_at and analysis')
        if not isinstance(record['analysis'], dict):
            raise ValueError('Analysis must be an object')
        key = uuid4().hex
        # JSON copy prevents later caller mutation and rejects NaN/unsupported types.
        self._records[key] = json.loads(json.dumps(record, allow_nan=False))
        return key

    def approve_report(self, report_id, reviewed_text, reviewer, *, applicability_checked):
        """Trusted human UI only, after displaying the exact text. Not a tool."""
        from machineear.agent_tools.models import SaveReportRevisionInput
        if report_id not in self._records:
            raise ValueError('Unknown report ID')
        # Validate the exact text without trimming or rewriting it.
        args = SaveReportRevisionInput(report_id=report_id, reviewed_text=reviewed_text, approval_id='pending')
        if not isinstance(reviewer, str) or not reviewer.strip() or applicability_checked is not True:
            raise PermissionError('Human reviewer and equipment applicability confirmation required')
        key = uuid4().hex
        self._approvals[key] = (report_id, _digest(args.reviewed_text), reviewer.strip())
        return key

    def execute(self, name, arguments):
        """Validate before dispatch and after execution. Failures raise, never fake success."""
        if name not in TOOLS:
            raise ValueError(f'Unknown tool: {name}')
        _, input_model, output_model, _ = TOOLS[name]
        args = (input_model.model_validate_json(arguments) if isinstance(arguments, str)
                else input_model.model_validate(arguments))
        result = getattr(self, '_' + name)(args)
        return output_model.model_validate(result).model_dump(mode='json')

    def _analyze_audio(self, args):
        if args.recording_id not in self._recordings:
            raise ValueError('Unknown recording ID; register an upload first')
        predictor = self.predictor
        if predictor is None:
            from machineear.audio_bridge import predict_audio
            predictor = predict_audio
        raw = predictor(self._recordings[args.recording_id], machine_type=args.machine_type,
                        machine_id=args.machine_id)
        if raw['machine_type'] != args.machine_type or raw['machine_id'] != args.machine_id:
            raise ValueError('Predictor returned the wrong equipment context')
        return AnalyzeAudioOutput(
            recording_id=args.recording_id, machine_type=raw['machine_type'], machine_id=raw['machine_id'],
            model=raw['model'], anomaly_score=raw['anomaly_score'], threshold=raw['threshold'],
            is_anomaly=raw['is_anomaly'], duration_seconds=raw['duration_seconds'],
            n_windows=raw['n_windows'], windows=raw['windows'])

    def _search_manuals(self, args):
        if self.retriever is None:
            from machineear.rag.retrieve_documents import LocalRetriever
            with LocalRetriever() as retriever:
                raw = retriever.search(args.query, args.machine_type, language=args.language, top_k=args.top_k)
        else:
            raw = self.retriever.search(args.query, args.machine_type, language=args.language, top_k=args.top_k)
        if len(raw['results']) > args.top_k:
            raise ValueError('Retriever exceeded requested result count')
        for p in raw['results']:
            if (p.get('citation_verified') is not True or p.get('needs_review')
                    or p.get('machine_scope') not in (args.machine_type, 'both')):
                raise ValueError('Retriever returned unverified or out-of-scope evidence')
        return SearchManualsOutput(status=raw['status'], passages=[{
            'chunk_id': p['chunk_id'], 'text': p['text'],
            'source_document': p['source_relative_path'], 'pdf_page_number': p['pdf_page_number'],
            'citation': p['citation'], 'semantic_similarity': p['semantic_similarity'],
            'citation_verified': p['citation_verified']} for p in raw['results']])

    def _save_report_revision(self, args):
        approval = self._approvals.get(args.approval_id)
        if (approval is None or approval[0] != args.report_id
                or approval[1] != _digest(args.reviewed_text)):
            raise PermissionError('Missing approval or report/text differs from human-approved content')
        record = self._records[args.report_id]
        # Generate an ID before saving so validation cannot fail after the write.
        revision_id = uuid4().hex
        from datetime import datetime, timezone
        output = SaveReportRevisionOutput(report_id=args.report_id, revision_id=revision_id,
            status='saved', reviewer=approval[2], saved_at=datetime.now(timezone.utc).isoformat(), approved=True)
        from machineear.review import save_review
        kwargs = {} if self.history_dir is None else {'directory': self.history_dir}
        saved = save_review({**copy.deepcopy(record), 'agent_revision_id': revision_id}, args.reviewed_text,
                    output.reviewer, approved=True, applicability=True, **kwargs)
        del self._approvals[args.approval_id]
        return output.model_copy(update={'saved_at': saved['review']['saved_at']})
