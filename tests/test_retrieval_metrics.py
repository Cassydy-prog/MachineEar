"""Known-answer retrieval metrics and benchmark orchestration without model assets."""

import json
import math
from pathlib import Path
import tempfile
import unittest

from machineear.rag.retrieval_metrics import score_ranking, summarize
from machineear.rag.benchmark_retrieval import benchmark, load_cases, save_report


def page(number):
    return {'source_relative_path': 'manual.pdf', 'pdf_page_number': number}


class MetricsTests(unittest.TestCase):
    def test_hand_calculated_ranking(self):
        # Slide example: relevant 2,5,9; results 7,2,4,5,1,9,3.
        relevance = {('manual.pdf', n): 1 for n in (2, 5, 9)}
        scores = score_ranking([page(n) for n in (7, 2, 4, 5, 1, 9, 3)], relevance, complete=True)
        self.assertEqual(scores['hit@1'], 0)
        self.assertEqual(scores['hit@3'], 1)
        self.assertEqual(scores['mrr@5'], .5)
        self.assertEqual(scores['precision@5'], .4)
        self.assertAlmostEqual(scores['recall@5'], 2 / 3)
        self.assertAlmostEqual(scores['ndcg@5'], (1/math.log2(3)+1/math.log2(5))/(1+1/math.log2(3)+.5))

    def test_incomplete_labels_do_not_claim_full_relevance_metrics(self):
        scores = score_ranking([page(2)], {('manual.pdf', 2): 1})
        self.assertEqual(scores['hit@5'], 1)
        for name in ('precision@5', 'recall@5', 'ndcg@5'):
            self.assertIsNone(scores[name])

    def test_duplicates_short_lists_and_graded_relevance(self):
        scores = score_ranking([page(1), page(1), page(2)],
                               {('manual.pdf', 1): 2, ('manual.pdf', 2): 1}, complete=True)
        self.assertEqual(scores['precision@5'], .4)
        self.assertEqual(scores['recall@5'], 1)
        self.assertEqual(scores['ndcg@5'], 1)

    def test_empty_ranking_zero_scores_and_invalid_labels(self):
        scores = score_ranking([], {('manual.pdf', 1): 1}, complete=True)
        self.assertTrue(all(v == 0 for v in scores.values()))
        for labels in ({}, {('manual.pdf', 1): 0}, {('manual.pdf', 1): -1}):
            with self.assertRaises(ValueError):
                score_ranking([], labels)
        with self.assertRaises(ValueError):
            score_ranking([], {('manual.pdf', 1): 1}, cutoffs=(0,))

    def test_separate_abstention_denominators_and_percentile(self):
        hit = score_ranking([page(1)], {('manual.pdf', 1): 1})
        miss = score_ranking([], {('manual.pdf', 1): 1})
        rows = [{'answerable': True, 'results': [page(1)], 'metrics': hit, 'latency_ms': 10},
                {'answerable': True, 'results': [], 'metrics': miss, 'latency_ms': 20},
                {'answerable': False, 'results': [], 'metrics': {}, 'latency_ms': 30}]
        summary = summarize(rows)
        self.assertEqual(summary['metrics']['hit@5'], .5)
        self.assertEqual(summary['correct_abstention_rate'], 1)
        self.assertEqual(summary['false_abstention_rate'], .5)
        self.assertEqual(summary['latency_median_ms'], 20)
        self.assertEqual(summary['latency_p95_ms'], 30)
        self.assertIsNone(summarize([])['latency_p95_ms'])

    def test_benchmark_routes_methods_exports_and_preserves_references(self):
        class Retriever:
            def __init__(self):
                self.calls = []
            def search(self, query, family, **kwargs):
                self.calls.append(kwargs)
                return {'results': [page(2)] if query == 'supported' else []}
        cases = [{'case_id': 'a', 'query': 'supported', 'machine_type': 'fan', 'language': 'en',
                  'answerable': True, 'judgments_complete': True,
                  'relevance': [{**page(2), 'grade': 2}]},
                 {'case_id': 'b', 'query': 'unsupported', 'machine_type': 'pump', 'language': 'fr',
                  'answerable': False, 'relevance': []}]
        retriever = Retriever()
        report = benchmark(retriever, cases)
        self.assertEqual(len(retriever.calls), 7)  # warmup + two questions x three methods
        for summary in report['summary'].values():
            self.assertEqual(summary['metrics']['mrr@5'], 1)
            self.assertEqual(summary['correct_abstention_rate'], 1)
        with tempfile.TemporaryDirectory() as folder:
            save_report(report, folder)
            self.assertEqual(json.loads((Path(folder)/'metrics.json').read_text())['evaluation_unit'],
                             'unique source document + physical PDF page')
            self.assertIn('ndcg@5', (Path(folder)/'scoreboard.csv').read_text())
            source = Path(folder)/'cases.json'
            source.write_text(json.dumps(cases))
            self.assertEqual(load_cases(source), cases)
            cases[0]['relevance'].append({**page(2), 'grade': 1})
            source.write_text(json.dumps(cases))
            with self.assertRaises(ValueError):
                load_cases(source)


class SearchMethodTests(unittest.TestCase):
    def test_rankings_preserve_shared_gate_deduplication_and_default(self):
        from unittest.mock import Mock, patch
        import numpy as np
        from machineear.rag.retrieve_documents import LocalRetriever
        retriever = LocalRetriever.__new__(LocalRetriever)
        retriever.encoder = Mock()
        retriever.encoder.encode.return_value = np.array([[1., 0.]])
        retriever.vectors = np.array([[.99, 0], [.95, 0], [.90, 0], [.10, 0]])
        retriever.chunks = [{**page(n + 1), 'page_id': str(n), 'machine_scope': 'fan',
                             'language': 'en', 'source_sha256': 'hash'} for n in range(4)]
        retriever.pages = {str(n): {} for n in range(4)}
        retriever.source_root = Path('.')
        retriever.connection = Mock()
        # BM25 ranks the weak semantic result first; shared cutoff must reject it.
        retriever.connection.execute.return_value = [(4,), (3,), (2,)]
        with patch('machineear.rag.retrieve_documents.detect_language', return_value=('en', 1)), \
             patch('machineear.rag.retrieve_documents.verify_passage') as verify, \
             patch('machineear.rag.retrieve_documents.file_hash', return_value='hash'), \
             patch.object(Path, 'is_file', return_value=True):
            default = retriever.search('bearing checks', 'fan', language='en')
            hybrid = retriever.search('bearing checks', 'fan', language='en', method='hybrid')
            semantic = retriever.search('bearing checks', 'fan', language='en', method='semantic')
            lexical = retriever.search('bearing checks', 'fan', language='en', method='bm25')
            self.assertEqual(default, hybrid)
            self.assertEqual([r['pdf_page_number'] for r in semantic['results']], [1, 2, 3])
            self.assertEqual([r['pdf_page_number'] for r in lexical['results']], [3, 2])
            self.assertTrue(verify.called)
            retriever.chunks[1]['page_id'] = '0'
            duplicate = retriever.search('bearing checks', 'fan', language='en', method='semantic')
            self.assertEqual([r['pdf_page_number'] for r in duplicate['results']], [1, 3])
            with self.assertRaises(ValueError):
                retriever.search('bearing checks', 'fan', method='invalid')
