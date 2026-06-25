import json
import os
import re
import random
from typing import List, Dict

DATABANK_PATH = os.path.join(os.path.dirname(__file__), '..', 'databank', 'master_databank.json')

STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
    'was', 'one', 'our', 'had', 'him', 'his', 'how', 'its', 'use', 'that',
    'this', 'with', 'have', 'from', 'they', 'will', 'been', 'what', 'when',
    'who', 'which', 'into', 'your', 'more', 'also', 'than', 'then', 'some',
    'would', 'there', 'their', 'about', 'should', 'could', 'does', 'dont',
    'isnt', 'arent', 'just', 'like', 'very', 'much'
}

_cache: List[Dict] = []


def _load() -> List[Dict]:
    global _cache
    if not _cache:
        try:
            with open(DATABANK_PATH, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = []
    return _cache


def _score(entry: Dict, tokens: set) -> float:
    text = ' '.join([
        entry.get('quote', ''),
        entry.get('context', ''),
        entry.get('category', ''),
        entry.get('krishna_angle', ''),
        ' '.join(entry.get('tags', []))
    ]).lower()

    score = 0.0
    for token in tokens:
        if token in text:
            # Weight exact tag matches higher
            if token in [t.lower() for t in entry.get('tags', [])]:
                score += 2.0
            else:
                score += 1.0
    return score


def retrieve_context(query: str, top_k: int = 3) -> str:
    databank = _load()
    if not databank:
        return ""

    tokens = set(re.findall(r'\b\w{3,}\b', query.lower())) - STOP_WORDS

    scored = [(s, e) for e in databank if (s := _score(e, tokens)) > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    top = scored[:top_k]
    if not top:
        top = [(0, e) for e in random.sample(databank, min(2, len(databank)))]

    parts = []
    for _, entry in top:
        line = f"[{entry.get('source', 'Wisdom')}] \"{entry.get('quote', '')}\""
        if entry.get('krishna_angle'):
            line += f"\n  → Krishna angle: {entry['krishna_angle']}"
        parts.append(line)

    return "\n\n".join(parts)
