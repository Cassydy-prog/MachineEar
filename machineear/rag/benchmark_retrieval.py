"""Compare local retrieval rankings using declared page references or custom qrels."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter

from machineear.rag.retrieval_metrics import score_ranking, summarize


def load_cases(path=None):
    if path is None:
        from machineear.rag.evaluate_retrieval import CASES
        return [{'case_id': key, 'machine_type': family, 'language': language, 'query': query,
                 'answerable': bool(source), 'judgments_complete': False,
                 'relevance': [{'source_relative_path': source, 'pdf_page_number': page, 'grade': 1}
                               for page in pages]}
                for key, family, language, query, source, pages in CASES]
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Cases must be a nonempty JSON list')
    ids = set()
    for case in cases:
        if not isinstance(case['case_id'], str) or case['case_id'] in ids:
            raise ValueError('Case IDs must be unique strings')
        ids.add(case['case_id'])
        if type(case['answerable']) is not bool or type(case.get('judgments_complete', False)) is not bool:
            raise ValueError('Answerable and judgments_complete must be booleans')
        if case['machine_type'] not in ('fan', 'pump') or not case['query'].strip():
            raise ValueError('Cases require a query and fan/pump family')
        relevance = judgments(case)
        if case['answerable'] != any(g > 0 for g in relevance.values()):
            raise ValueError('Answerability must agree with positive relevance judgments')
    return cases


def judgments(case):
    result = {}
    for item in case['relevance']:
        key = item['source_relative_path'], item['pdf_page_number']
        grade = item['grade']
        if (not isinstance(key[0], str) or not key[0] or type(key[1]) is not int or key[1] < 1
                or type(grade) is not int or grade not in (0, 1, 2) or key in result):
            raise ValueError('Judgments need unique source/page keys and integer grades 0..2')
        result[key] = grade
    return result


def benchmark(retriever, cases, *, min_similarity=.82, warmup=True):
    """All methods share the production semantic gate and page deduplication.

    BM25 is therefore semantic-gated BM25, not a pure lexical baseline. Warmup
    is excluded; timed calls include query encoding and citation verification.
    Method order rotates to reduce systematic first-call/cache advantages.
    """
    if not cases:
        raise ValueError('At least one case is required')
    methods = ('bm25', 'semantic', 'hybrid')
    if warmup:
        case = cases[0]
        retriever.search(case['query'], case['machine_type'], language=case['language'],
                         top_k=5, method='hybrid', min_similarity=min_similarity)
    runs = {method: [] for method in methods}
    for number, case in enumerate(cases):
        order = methods[number % 3:] + methods[:number % 3]
        for method in order:
            start = perf_counter()
            response = retriever.search(case['query'], case['machine_type'], language=case['language'],
                                        top_k=5, method=method, min_similarity=min_similarity)
            elapsed = (perf_counter() - start) * 1000
            metrics = score_ranking(response['results'], judgments(case),
                                    complete=case.get('judgments_complete', False)) if case['answerable'] else {}
            runs[method].append({**case, 'results': response['results'], 'metrics': metrics,
                                 'latency_ms': elapsed})
    return {'purpose': 'Development benchmark unless a separately held-out question set is supplied',
            'evaluation_unit': 'unique source document + physical PDF page',
            'minimum_semantic_similarity': min_similarity,
            'bm25_note': 'BM25 ranking with shared semantic gate; not a pure lexical baseline',
            'latency_note': 'One excluded warmup; rotated method order; per-call encoding and citation verification included',
            'cases_sha256': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
            'summary': {method: summarize(rows) for method, rows in runs.items()}, 'runs': runs}


def save_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = [{'method': method, **{k: v for k, v in summary.items() if k != 'metrics'}, **summary['metrics']}
            for method, summary in report['summary'].items()]
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (output / 'scoreboard.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, help='Custom JSON cases with page relevance judgments')
    parser.add_argument('--output-dir', type=Path, default=Path('results/rag/benchmark'))
    parser.add_argument('--min-similarity', type=float, default=.82)
    args = parser.parse_args(argv)
    cases = load_cases(args.cases)
    from machineear.rag.retrieve_documents import LocalRetriever
    with LocalRetriever() as retriever:
        report = benchmark(retriever, cases, min_similarity=args.min_similarity)
        report['index_manifest'] = retriever.manifest
    save_report(report, args.output_dir)
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
