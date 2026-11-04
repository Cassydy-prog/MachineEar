"""Human evaluation of saved MachineEar reports; no external model call."""
import csv
import hashlib
import io
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
ANALYSES = ROOT / 'results' / 'web_analyses'
REVIEWS = ROOT / 'results' / 'report_evaluations'
router = APIRouter()
LOCK = threading.Lock()
CRITERIA = ('audio_fidelity', 'source_support', 'citation_accuracy', 'context_relevance')


def valid_id(value):
    if len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise HTTPException(404, 'Analysis not found')
    return value


def read_analysis(identifier):
    path = ANALYSES / f'{valid_id(identifier)}.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise HTTPException(404, 'Analysis not found') from None


def digest(record):
    # Snapshot includes the exact report and saved evidence, not chat history.
    data = {k: record.get(k) for k in ('report', 'report_data', 'analysis', 'notes', 'equipment', 'quality', 'report_prompt_version')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Review(BaseModel):
    report_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=1, max_length=100)
    audio_fidelity: int = Field(ge=0, le=2, strict=True)
    source_support: int = Field(ge=0, le=2, strict=True)
    citation_accuracy: int | None = Field(default=None, ge=0, le=2, strict=True)
    context_relevance: int = Field(ge=0, le=2, strict=True)
    unsupported_claims: int = Field(ge=0, strict=True)
    cited_claims_checked: int = Field(ge=0, strict=True)
    cited_claims_supported: int = Field(ge=0, strict=True)
    cited_claims_unverifiable: int = Field(default=0, ge=0, strict=True)
    notes: str = Field(min_length=1, max_length=8000)


@router.get('/evaluation', include_in_schema=False)
def evaluation_page():
    return FileResponse(ROOT / 'frontend' / 'evaluation.html')


@router.get('/api/evaluations')
def inventory():
    rows = []
    for path in ANALYSES.glob('*.json'):
        try:
            record = read_analysis(path.stem)
            version = digest(record)
            reviews = []
            for p in sorted((REVIEWS / path.stem).glob('*.json')):
                reviews.append(json.loads(p.read_text(encoding='utf-8')))
            rows.append({'id': path.stem, 'filename': record.get('filename'),
                         'machine': record.get('analysis', {}).get('audio', {}),
                         'created_at': record.get('created_at', ''), 'report_hash': version,
                         'reviews': [{'reviewer': r['reviewer'], 'created_at': r['created_at'],
                                      'current': r['report_hash'] == version} for r in reviews]})
        except (ValueError, OSError, HTTPException):
            continue
    return sorted(rows, key=lambda r: r['created_at'], reverse=True)


@router.get('/api/evaluations/export.csv')
def export():
    fields = ['review_id', 'analysis_id', 'created_at', 'reviewer', 'report_hash', 'current_report',
              *CRITERIA, 'unsupported_claims', 'cited_claims_checked', 'cited_claims_supported',
              'cited_claims_unverifiable', 'notes']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for p in sorted(REVIEWS.glob('*/*.json')):
        try:
            review = json.loads(p.read_text(encoding='utf-8'))
            try:
                current = digest(read_analysis(review['analysis_id'])) == review['report_hash']
            except HTTPException:
                current = False
            row = {k: review.get(k, '') for k in fields}
            row['current_report'] = current
            # Avoid spreadsheet formula execution in user-entered text.
            for key in ('reviewer', 'notes'):
                if str(row[key]).lstrip().startswith(('=', '+', '-', '@')):
                    row[key] = "'" + str(row[key])
            writer.writerow(row)
        except (ValueError, OSError, KeyError):
            continue
    return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="machineear_evaluations.csv"'})


@router.get('/api/evaluations/{identifier}')
def evidence(identifier: str):
    record = read_analysis(identifier)
    return {'record': record, 'report_hash': digest(record)}


@router.post('/api/evaluations/{identifier}')
def save_review(identifier: str, body: Review):
    if not body.reviewer.strip() or not body.notes.strip():
        raise HTTPException(422, 'Reviewer and evidence notes are required')
    if body.cited_claims_supported > body.cited_claims_checked:
        raise HTTPException(422, 'Supported claims cannot exceed checked claims')
    if body.cited_claims_checked == 0 and body.citation_accuracy is not None:
        raise HTTPException(422, 'Use non-verifiable/not applicable when no citation was checked')
    if body.cited_claims_checked > 0 and body.citation_accuracy is None:
        raise HTTPException(422, 'Score the citations that were checked')
    with LOCK:
        record = read_analysis(identifier)
        if body.report_hash != digest(record):
            raise HTTPException(409, 'Report changed. Reload before evaluating.')
        directory = REVIEWS / identifier
        directory.mkdir(parents=True, exist_ok=True)
        item = body.model_dump()
        item.update(review_id=uuid4().hex, analysis_id=identifier,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    method='human_rubric_v1', snapshot=record)
        target = directory / f"{item['review_id']}.json"
        temporary = target.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(item, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return {'saved': True, 'review_id': item['review_id']}
