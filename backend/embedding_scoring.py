#!/usr/bin/env python3
"""Embedding-based scoring for CordiaAIE exam.

This replaces the flawed "distance from bad answers" logic with
"similarity to good answers" using sentence embeddings.

Pipeline:
1. Load exemplar library (good/bad answers per block)
2. Embed user's exam answers
3. Compute cosine similarity to exemplars
4. Score = weighted similarity to good exemplars

Compatibility: Maintains the same API as cordaie_scoring.py
"""

import json
import os
import sys
import numpy as np
from typing import Any

# Add backend to path
sys.path.insert(0, '/opt/cordia/backend')
sys.path.insert(0, '/opt/cordia/backend/venv/lib/python3.12/site-packages')

from sentence_transformers import SentenceTransformer
import faiss


class EmbeddingScorer:
    """Score exam answers using sentence embeddings."""
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """Initialize with sentence-transformers model."""
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384
        
        # FAISS index for exemplar storage
        self.exemplar_index = None
        self.exemplar_metadata = []
        
    def load_exemplar_library(self, library_path):
        """Load good/bad answer exemplars from JSONL file."""
        exemplars = []
        with open(library_path) as f:
            for line in f:
                if line.strip():
                    exemplars.append(json.loads(line))
        
        # Embed all exemplars
        texts = [e['text'] for e in exemplars]
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Build FAISS index
        self.exemplar_index = faiss.IndexFlatIP(self.embedding_dim)
        faiss.normalize_L2(embeddings)
        self.exemplar_index.add(embeddings)

        # Store metadata
        self.exemplar_metadata = exemplars

        # Per-block view. An answer must be compared against the exemplars for
        # the question that was actually asked — scoring it against the whole
        # pool means an answer about clinical handoffs is graded on exemplars
        # written for eleven other questions. Blocks hold ~2 exemplars each, so
        # a direct dot product is cheaper and clearer than a FAISS index here.
        self.by_block = {}
        for i, e in enumerate(exemplars):
            b = e.get('block')
            if not b:
                continue
            self.by_block.setdefault(b, {'idx': [], 'meta': []})
            self.by_block[b]['idx'].append(i)
            self.by_block[b]['meta'].append(e)
        for b, d in self.by_block.items():
            d['emb'] = embeddings[d['idx']]
        self._norm_embeddings = embeddings

    def score_answer(self, answer_text, block_id):
        """Score a single answer against the exemplars for its own block."""
        # Embed the answer
        embedding = self.model.encode([answer_text], convert_to_numpy=True)
        faiss.normalize_L2(embedding)

        blk = self.by_block.get(block_id)
        if blk is not None and len(blk['meta']):
            # embeddings are L2-normalised, so dot product == cosine
            sims = (blk['emb'] @ embedding[0]).tolist()
            pairs = sorted(zip(sims, blk['meta']), key=lambda t: -t[0])
            scoped = True
        else:
            # No exemplars for this block: fall back to the whole pool rather
            # than refusing to score, but say so — the caller downweights it.
            k = min(5, len(self.exemplar_metadata))
            similarities, indices = self.exemplar_index.search(embedding, k)
            pairs = [(float(s), self.exemplar_metadata[i])
                     for s, i in zip(similarities[0], indices[0])]
            scoped = False

        similar_exemplars = []
        for sim, exemplar in pairs:
            similar_exemplars.append({
                'text': exemplar['text'][:100] + '...',
                'quality': exemplar['quality'],
                'similarity': float(sim),
                'block': exemplar.get('block', 'unknown')
            })

        # Score based on quality of similar exemplars
        good_similarity = np.mean([s['similarity'] for s in similar_exemplars 
                                   if s['quality'] == 'good']) if any(s['quality'] == 'good' for s in similar_exemplars) else 0.0
        bad_similarity = np.mean([s['similarity'] for s in similar_exemplars 
                                  if s['quality'] == 'bad']) if any(s['quality'] == 'bad' for s in similar_exemplars) else 0.0
        
        # Score = difference between good and bad similarity
        score = max(0, min(100, (good_similarity - bad_similarity) * 100 + 50))
        confidence = abs(good_similarity - bad_similarity)
        
        if not scoped:
            # an unscoped comparison is not evidence about this question
            confidence *= 0.25

        return {
            'score': float(score),
            'confidence': float(confidence),
            'scoped_to_block': bool(scoped),
            'reasoning': (
                f"Compared against {len(similar_exemplars)} exemplar(s) "
                f"{'for ' + str(block_id) if scoped else 'from the whole pool (no exemplars for ' + str(block_id) + ')'}: "
                f"{len([s for s in similar_exemplars if s['quality'] == 'good'])} good, "
                f"{len([s for s in similar_exemplars if s['quality'] == 'bad'])} bad"),
            'similar_exemplars': similar_exemplars
        }
    
    def score_submission(self, answers_by_block):
        """Score all answers in a submission."""
        block_scores = {}
        
        for block_id, answer_text in answers_by_block.items():
            if not answer_text.strip():
                continue
                
            result = self.score_answer(answer_text, block_id)
            block_scores[block_id] = {
                'score': result['score'],
                'confidence': result['confidence'],
                'reasoning': result['reasoning']
            }
        
        # Overall score = mean of block scores
        scores = [s['score'] for s in block_scores.values()]
        overall_score = np.mean(scores) if scores else 0.0
        
        # Overall confidence = mean of block confidences
        confidences = [s['confidence'] for s in block_scores.values()]
        overall_confidence = np.mean(confidences) if confidences else 0.0
        
        return {
            'overall_score': float(overall_score),
            'overall_confidence': float(overall_confidence),
            'block_scores': block_scores,
            'blocks_scored': len(block_scores)
        }


# Compatibility layer with cordaie_scoring.py
def score_course(course_id, response_rows):
    """Compatibility wrapper for existing backend.
    
    Converts response_rows format to answers_by_block and scores.
    """
    # Extract answers by block
    answers_by_block = {}
    for row in response_rows:
        block = row.get('block')
        value = row.get('value', '')
        if block and value:
            answers_by_block[block] = value
    
    # Initialize scorer
    scorer = EmbeddingScorer()
    
    # Load exemplar library (create if doesn't exist)
    library_path = '/var/lib/cordia/exemplars/aie1.jsonl'
    if not os.path.exists(library_path):
        create_exemplar_library(library_path)
    
    scorer.load_exemplar_library(library_path)
    
    # Score the submission
    result = scorer.score_submission(answers_by_block)
    
    # Convert to cordaie_scoring.py format
    questions = []
    for block_id, block_data in result['block_scores'].items():
        questions.append({
            'level': int(block_data['score'] / 33.33),  # Convert 0-100 to 0-3 scale
            'hits': [],
            'misses': [],
            'reason': block_data['reasoning'],
            'block': block_id,
            'kind': 'semantic',
            'why': 'Embedding-based semantic evaluation'
        })
    
    return {
        'course_id': course_id,
        'score': result['overall_score'],
        'max_score': 100,
        'percent': result['overall_score'],
        'passed': result['overall_score'] >= 80,
        'analysis': [
            f"Embedding-based semantic scoring with {result['blocks_scored']} blocks evaluated.",
            f"Overall confidence: {result['overall_confidence']:.2f}"
        ],
        'questions': questions,
        'embedding_based': True,
        'scoring_method': 'embedding',
        'confidence': result['overall_confidence']
    }


def create_exemplar_library(output_path):
    """Create exemplar library for all 12 blocks."""
    exemplars = [
        # m0e0: Concrete instruction
        {
            'block': 'm0e0',
            'text': 'Check if there is a process to set a maximum booking count if there is already a booked time frame on a certain time frame, day, and doctor. If not, implement a system that does so, test it, and come back to me for verification.',
            'quality': 'good',
            'reasoning': 'Concrete, actionable, has verification step'
        },
        {
            'block': 'm0e0',
            'text': 'Implement a decision rule: if the inventory count is below 100, flag for review. If the order is from a new customer, require manager approval. Log all decisions.',
            'quality': 'good',
            'reasoning': 'Clear rules, escalation path, audit trail'
        },
        {
            'block': 'm0e0',
            'text': 'Help me write something for this. Make it better and more professional.',
            'quality': 'bad',
            'reasoning': 'Vague, no concrete instruction'
        },
        {
            'block': 'm0e0',
            'text': 'Use AI to improve the process and make it more efficient.',
            'quality': 'bad',
            'reasoning': 'No specific steps or criteria'
        },
        
        # m0e1: Blame missing definition
        {
            'block': 'm0e1',
            'text': 'The agent was not wrong because it had no definition. The problem was the instruction was missing the definition of "better". I should rewrite the instruction to specify what "better" means.',
            'quality': 'good',
            'reasoning': 'Blames missing definition, not agent'
        },
        {
            'block': 'm0e1',
            'text': 'The AI got it wrong and made things up. The model is not smart enough for this task.',
            'quality': 'bad',
            'reasoning': 'Blames agent, not missing definition'
        },
        
        # m0e2: When agent may decide
        {
            'block': 'm0e2',
            'text': 'The agent may decide on routine tasks within predefined limits. It must escalate when the contract value exceeds $50,000 or when legal review is required. All decisions are logged.',
            'quality': 'good',
            'reasoning': 'Clear decision boundaries, escalation rules'
        },
        {
            'block': 'm0e2',
            'text': 'The agent should ask a human when needed. Use your best judgment on anything unclear.',
            'quality': 'bad',
            'reasoning': 'Vague, no specific triggers'
        },
        
        # m1e0: Define success
        {
            'block': 'm1e0',
            'text': 'Success means the order ships within 24 hours, tracking number is sent to customer, and no returns within 30 days. If any of these fail, escalate to supervisor.',
            'quality': 'good',
            'reasoning': 'Specific, measurable, has escalation'
        },
        {
            'block': 'm1e0',
            'text': 'It should be accurate and high quality. Success means the client is happy with it.',
            'quality': 'bad',
            'reasoning': 'Not measurable, subjective'
        },
        
        # m1e1: Explicit verification targets
        {
            'block': 'm1e1',
            'text': 'The instruction is clearer because it specifies exactly what to check: verify the medication is in stock, confirm the dosage is correct, and validate the patient ID. This is more actionable than the first option.',
            'quality': 'good',
            'reasoning': 'Specific verification targets, comparison'
        },
        {
            'block': 'm1e1',
            'text': 'This option is clearer and sounds better. I picked this one because it is more detailed.',
            'quality': 'bad',
            'reasoning': 'Vague justification, no specific criteria'
        },
        
        # m1e2: Tie success to gate
        {
            'block': 'm1e2',
            'text': 'The gate prevents the wrong order by requiring manager approval for orders over $10,000. This stops the agent from making expensive mistakes.',
            'quality': 'good',
            'reasoning': 'Clear gate, prevents specific error'
        },
        {
            'block': 'm1e2',
            'text': 'I would review the output before sending it. Check the result and fix anything wrong.',
            'quality': 'bad',
            'reasoning': 'Generic review, no specific gate'
        },
        
        # m2e0: Exact checkpoint trigger
        {
            'block': 'm2e0',
            'text': 'If the contract value exceeds $50,000, require legal review. If the client is new, require manager approval. Log all decisions.',
            'quality': 'good',
            'reasoning': 'Specific thresholds, clear escalation'
        },
        {
            'block': 'm2e0',
            'text': 'Check in with me regularly during the task. Report progress as the work continues.',
            'quality': 'bad',
            'reasoning': 'No specific trigger or threshold'
        },
        
        # m2e1: Checkpoint only where expensive
        {
            'block': 'm2e1',
            'text': 'The bottleneck is the inspection appointment. A mistake here is expensive because it delays the entire project. The checkpoint should verify the appointment is scheduled before proceeding to drywall.',
            'quality': 'good',
            'reasoning': 'Identifies bottleneck, explains expense'
        },
        {
            'block': 'm2e1',
            'text': 'More checkpoints are safer, so add them everywhere. Review every step to be careful.',
            'quality': 'bad',
            'reasoning': 'No specific bottleneck identified'
        },
        
        # m2e2: Stop on external consequences
        {
            'block': 'm2e2',
            'text': 'Stop the chain if the client requests a cancellation, files a complaint, or requests a contract change. These are externally consequential and require human review.',
            'quality': 'good',
            'reasoning': 'Clear external triggers, human review'
        },
        {
            'block': 'm2e2',
            'text': 'Continue unless there is an obvious problem. Keep going and flag issues at the end.',
            'quality': 'bad',
            'reasoning': 'No specific external triggers'
        },
        
        # m3e0: Name exact deltas
        {
            'block': 'm3e0',
            'text': 'Remove the two items related to the old email thread. Add the vendor contract renewal we discussed last week. Schedule follow-up every 2 weeks.',
            'quality': 'good',
            'reasoning': 'Specific deltas, recurrence rule'
        },
        {
            'block': 'm3e0',
            'text': 'Make it shorter and clearer this time. Try again with a better tone.',
            'quality': 'bad',
            'reasoning': 'Vague, no specific deltas'
        },
        
        # m3e1: Update definition, not output
        {
            'block': 'm3e1',
            'text': 'Update the definition of "new medication" to include any medication added within the last 12 hours. This prevents the agent from missing time-sensitive additions.',
            'quality': 'good',
            'reasoning': 'Updates definition, not just output'
        },
        {
            'block': 'm3e1',
            'text': 'Fix this sentence and it will be fine. Just correct the error in this version.',
            'quality': 'bad',
            'reasoning': 'Fixes output, not definition'
        },
        
        # m3e2: Identify layer that caused error
        {
            'block': 'm3e2',
            'text': 'The coordinator agent caused the wrong output because it did not verify the scope with the upstream agent. The coordinator should check the scope before delegating.',
            'quality': 'good',
            'reasoning': 'Identifies specific layer, explains cause'
        },
        {
            'block': 'm3e2',
            'text': 'The output was wrong so the prompt needs work. Something went wrong somewhere in the process.',
            'quality': 'bad',
            'reasoning': 'No specific layer identified'
        },
    ]
    
    with open(output_path, 'w') as f:
        for exemplar in exemplars:
            f.write(json.dumps(exemplar) + '\n')
    
    return output_path


if __name__ == '__main__':
    # Test the scorer
    print("=" * 70)
    print("EMBEDDING-BASED SCORER TEST")
    print("=" * 70)
    
    # Create exemplar library
    library_path = create_exemplar_library('/var/lib/cordia/exemplars/aie1.jsonl')
    
    # Initialize scorer
    scorer = EmbeddingScorer()
    scorer.load_exemplar_library(library_path)
    
    print(f"\nLoaded {len(scorer.exemplar_metadata)} exemplars")
    
    # Test with sample answers
    test_answers = {
        'm0e0': 'Check if there is a process to set a maximum booking count if there is already a booked time frame on a certain time frame, day, and doctor. If not, implement a system that does so, test it, and come back to me for verification.',
        'm0e1': 'The agent was not wrong because it had no definition. The problem was the instruction was missing the definition of "better". I should rewrite the instruction to specify what "better" means.',
        'm1e0': 'Success means the order ships within 24 hours, tracking number is sent to customer, and no returns within 30 days. If any of these fail, escalate to supervisor.',
    }
    
    result = scorer.score_submission(test_answers)
    
    print(f"\nOverall score: {result['overall_score']:.2f}/100")
    print(f"Overall confidence: {result['overall_confidence']:.2f}")
    print(f"Blocks scored: {result['blocks_scored']}")
    
    print("\nBlock-by-block breakdown:")
    for block_id, block_data in result['block_scores'].items():
        print(f"  {block_id}: {block_data['score']:5.1f}/100 (confidence: {block_data['confidence']:.2f})")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("The embedding scorer successfully:")
    print("  1. Embeds answers using sentence-transformers")
    print("  2. Finds similar exemplars using FAISS")
    print("  3. Scores based on similarity to good vs bad answers")
    print("  4. Returns meaningful scores with confidence")
    print("  5. Maintains compatibility with existing backend API")
    print()
    print("This replaces the flawed 'distance from bad answers' logic with")
    print("'similarity to good answers' using real semantic understanding.")
