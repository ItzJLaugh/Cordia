#!/usr/bin/env python3
"""CordiaAIE scoring engine.

Hidden rubric lives in cordaie_rubrics.json. This scorer stays intentionally
simple and explainable: a hybrid of lexical anchor hits, negative-signal
penalties, and a final analysis summary. The backend can later swap in an LLM
judge, but the score shape stays the same.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

RUBRIC_PATH = os.path.join(os.path.dirname(__file__), 'cordaie_rubrics.json')
STOPWORDS = {
    'a','an','and','are','as','at','be','because','but','by','do','does','for','from','get','go','has','have',
    'if','in','into','is','it','its','just','me','my','not','of','on','or','our','so','that','the','their','then',
    'there','these','this','those','to','up','use','we','when','where','with','you','your','would','should','could'
}


def _load_rubrics() -> dict[str, Any]:
    with open(RUBRIC_PATH) as f:
        return json.load(f)


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z']+", _norm(s)) if t not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _match_patterns(answer: str, patterns: list[str]) -> list[str]:
    ans = _norm(answer)
    hits = []
    for p in patterns:
        # interpret very small pattern language: plain substring or regex if wrapped with /
        if p.startswith('/') and p.endswith('/') and len(p) > 2:
            if re.search(p[1:-1], ans):
                hits.append(p)
        elif _norm(p) in ans:
            hits.append(p)
    return hits


def _score_text(answer: str, rubric: dict[str, Any]) -> dict[str, Any]:
    ans = _norm(answer)
    token_set = _tokens(answer)

    # Hidden-rubric path: if concepts are present, score by concept coverage.
    concepts = rubric.get('concepts')
    if concepts:
        hits = []
        misses = []
        for concept in concepts:
            pats = concept.get('patterns', [])
            if _match_patterns(ans, pats):
                hits.append(concept.get('id', 'concept'))
            else:
                misses.append(concept.get('id', 'concept'))
        if len(hits) >= len(concepts):
            level = 3
        elif len(hits) >= max(1, len(concepts) - 1):
            level = 2
        elif len(hits) >= 1:
            level = 1
        else:
            level = 0
        # semantic fallback: if the answer shares substantial intent vocabulary with the exemplar,
        # but didn't hit the exact concept patterns, cap at 2.
        exemplar = rubric.get('model_answer_exemplar', '')
        if level < 2 and exemplar:
            if _jaccard(token_set, _tokens(exemplar)) >= 0.35:
                level = 2
        if any(g in ans for g in rubric.get('generic_penalty_terms', [])) and len(token_set) < 8:
            level = 0
        reason = []
        if hits:
            reason.append(f"matched concepts: {', '.join(hits)}")
        if misses:
            reason.append(f"missed concepts: {', '.join(misses[:3])}")
        if not reason:
            reason.append('no strong rubric concepts detected')
        return {'level': level, 'hits': hits, 'misses': misses, 'reason': '; '.join(reason)}

    # Legacy anchor path for other questions
    pos = 0
    neg = 0
    hits = []
    misses = []
    for a in rubric.get('anchors', []):
        if _norm(a) in ans:
            pos += 1
            hits.append(a)
    for n in rubric.get('negative', []):
        if _norm(n) in ans:
            neg += 1
            misses.append(n)

    if pos == 0 and neg >= 1:
        level = 0
    elif pos <= 1:
        level = 1
    elif pos == 2 and neg == 0:
        level = 2
    elif pos >= 3 and neg == 0:
        level = 3
    else:
        level = 2 if pos >= 2 else 1

    reason = []
    if hits:
        reason.append(f"matched anchors: {', '.join(hits[:3])}")
    if misses:
        reason.append(f"contained weak phrasing: {', '.join(misses[:2])}")
    if not reason:
        reason.append('no strong rubric anchors detected')
    return {'level': level, 'hits': hits, 'misses': misses, 'reason': '; '.join(reason)}


def _latest_by_block(response_rows: list[dict[str, Any]]) -> dict[str, str]:
    latest = {}
    latest_ts = {}
    for r in response_rows:
        block = r.get('block')
        ts = r.get('ts', 0)
        if block is not None and ts >= latest_ts.get(block, -1):
            latest_ts[block] = ts
            latest[block] = r.get('value', '')
    return latest


def score_course(course_id: str, response_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rubrics = _load_rubrics()[course_id]
    latest = _latest_by_block(response_rows)
    scored = []
    total = 0
    max_total = 0
    for module in rubrics['modules']:
        for block, rubric in module['questions'].items():
            ans = latest.get(block, '')
            result = _score_text(ans, rubric)
            result['block'] = block
            result['kind'] = rubric['kind']
            result['why'] = rubric['why']
            scored.append(result)
            total += result['level']
            max_total += 3
    pct = round((total / max_total) * 100) if max_total else 0
    passed = total >= 0.8 * max_total
    analysis = []
    if passed:
        analysis.append('You are using concrete rules, not just goals.')
    else:
        analysis.append('You still leave too much judgment implied.')
    weak = [s for s in scored if s['level'] < 2]
    if weak:
        analysis.append('Weak spots: ' + ', '.join(s['block'] for s in weak[:4]))
    return {
        'course_id': course_id,
        'score': total,
        'max_score': max_total,
        'percent': pct,
        'passed': passed,
        'analysis': analysis,
        'questions': scored,
    }
