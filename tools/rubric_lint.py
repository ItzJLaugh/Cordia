#!/usr/bin/env python3
"""Rubric anchor lint — enforce authoring standard A7 mechanically.

A7 states the test plainly:

    "For every cascade criterion, apply this test: could a learner hit this by
     wording their instruction cleverly, without knowing anything about the
     situation? If yes, cut the criterion."

An anchor that appears verbatim inside its own prompt fails that test by
construction: the learner can hit it by echoing the question back. So can a
stopword. The rubric was written without this check applied, and 14 of 70
anchors (20%) fail it — which is why a learner who answered in their own words
scored 1/3 while one who parroted the prompt's nouns scored higher.

This is a lint, not a rewrite. It reports; a human decides. Run:

    python3 tools/rubric_lint.py            # report
    python3 tools/rubric_lint.py --strict   # exit 1 if any anchor fails
"""
import json
import re
import sys
import pathlib

ROOT = pathlib.Path('/opt/cordia')
RUBRICS = ROOT / 'backend/cordaie_rubrics.json'
COURSE = ROOT / 'web/assets/course-content-aie1.js'

# words that carry no evidence about reasoning
STOPWORDS = {
    'if', 'and', 'or', 'the', 'a', 'an', 'to', 'is', 'it', 'be', 'do', 'not',
    'of', 'in', 'on', 'for', 'with', 'that', 'this', 'you', 'your', 'as',
    'at', 'by', 'from', 'so', 'then', 'when', 'what', 'how', 'why', 'can',
}


def load_prompts():
    """block id -> its prompt text, from the live course content."""
    src = COURSE.read_text()
    prompts = {}
    modules = re.findall(r'"exercises":\s*\[(.*?)\]\s*\}', src, re.S)
    for mi, block in enumerate(modules):
        for ei, p in enumerate(re.findall(r'"prompt":\s*"((?:[^"\\]|\\.)*)"', block)):
            prompts[f'm{mi}e{ei}'] = p.lower()
    return prompts


def lint():
    rub = json.loads(RUBRICS.read_text())
    course = rub.get('aie1', rub)
    prompts = load_prompts()

    findings, total = [], 0
    for module in course.get('modules', []):
        for block, rb in (module.get('questions') or {}).items():
            prompt = prompts.get(block, '')
            for kind in ('anchors', 'negative'):
                for a in rb.get(kind, []):
                    total += 1
                    t = str(a).strip().lower()
                    if t in STOPWORDS:
                        findings.append((block, kind, a, 'stopword — carries no evidence'))
                    elif prompt and t in prompt:
                        findings.append((block, kind, a,
                                         'appears in its own prompt — hittable by echoing the question'))
    return findings, total


def main():
    findings, total = lint()
    if findings:
        w = max(len(f[2]) for f in findings)
        print(f'{"block":7} {"field":9} {"anchor":<{w}}  reason')
        print('-' * (7 + 9 + w + 40))
        for block, kind, a, why in sorted(findings):
            print(f'{block:7} {kind:9} {a:<{w}}  {why}')
    pct = 100 * len(findings) / total if total else 0
    print(f'\n{len(findings)} of {total} criteria fail A7 ({pct:.0f}%)')
    if findings:
        print('\nThese do not measure reasoning. Replace each with the move the learner')
        print('has to MAKE rather than the noun they can repeat — e.g. for m2e1 the')
        print('evidence is not "drywall", it is naming why that date specifically')
        print('(fixed inspection, irreversible) over any other date.')
    if '--strict' in sys.argv and findings:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
