"""Dependency-free page-level retrieval metrics; no model or network side effects."""

import math
import statistics


def page_key(result):
    return result['source_relative_path'], result['pdf_page_number']


def score_ranking(results, relevance, *, complete=False, cutoffs=(1, 3, 5)):
    """Score unique physical pages. Relevance maps (source, page) to grades 0..2.

    Incomplete reference judgments support reference Hit/MRR only. Precision,
    recall and nDCG remain None until the caller declares exhaustive judgments.
    Missing results count as nonrelevant for fixed-k precision. Duplicate pages
    count once. Unanswerable questions are handled separately by summarize().
    """
    if any(type(k) is not int or k < 1 for k in cutoffs):
        raise ValueError('Cutoffs must be positive integers')
    if any(type(g) is not int or not 0 <= g <= 2 for g in relevance.values()):
        raise ValueError('Relevance grades must be integers from 0 to 2')
    pages = list(dict.fromkeys(page_key(r) for r in results))
    positives = {p for p, grade in relevance.items() if grade > 0}
    if not positives:
        raise ValueError('Answerable questions need at least one relevant page')
    scores = {}
    for k in cutoffs:
        grades = [relevance.get(p, 0) for p in pages[:k]]
        hits = sum(g > 0 for g in grades)
        rank = next((i for i, g in enumerate(grades, 1) if g > 0), None)
        ideal = sorted(relevance.values(), reverse=True)[:k]
        dcg = sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(grades, 1))
        idcg = sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(ideal, 1))
        scores.update({f'hit@{k}': float(hits > 0), f'mrr@{k}': 1 / rank if rank else 0.0,
                       f'precision@{k}': hits / k if complete else None,
                       f'recall@{k}': hits / len(positives) if complete else None,
                       f'ndcg@{k}': dcg / idcg if complete else None})
    return scores


def summarize(cases):
    """Macro-average answerable questions; keep abstention denominators separate."""
    answerable = [c for c in cases if c['answerable']]
    unsupported = [c for c in cases if not c['answerable']]
    metrics = {}
    for name in (answerable[0]['metrics'] if answerable else {}):
        values = [c['metrics'][name] for c in answerable]
        # Never silently average only the fully labelled subset.
        metrics[name] = statistics.mean(values) if all(v is not None for v in values) else None
    times = sorted(c['latency_ms'] for c in cases)
    return {'query_count': len(cases), 'answerable_count': len(answerable),
            'unsupported_count': len(unsupported), 'metrics': metrics,
            'correct_abstention_rate': (sum(not c['results'] for c in unsupported) / len(unsupported)
                                        if unsupported else None),
            'false_abstention_rate': (sum(not c['results'] for c in answerable) / len(answerable)
                                      if answerable else None),
            'latency_median_ms': statistics.median(times) if times else None,
            'latency_p95_ms': times[math.ceil(.95 * len(times)) - 1] if times else None}
