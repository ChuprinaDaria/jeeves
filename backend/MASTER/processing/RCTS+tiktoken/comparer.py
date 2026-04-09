import json, re, math, statistics as stats
from pathlib import Path
import tiktoken
from collections import Counter

# ---------- CONFIG ----------
TARGET_SIZE = 100          # your intended token size
OVERLAP_TOK = 20          # your intended overlap
ENC_NAME = "cl100k_base"   # tokenizer encoding
SEPARATORS = ["\n\n", "\n", " ", ".", ",", "!", "?", ":", ";", "\u200b", "\uff0c", "\u3001", "\uff0e", "\u3002"]

# ---------- IO ----------
orig_text = Path("test.txt").read_text(encoding="utf-8")
chunks_data = json.loads(Path("out1.json").read_text(encoding="utf-8"))  # <- your token-aware chunks
# normalize chunk list
chunks = []
for x in chunks_data:
    if isinstance(x, dict):
        chunks.append(x.get("text") or x.get("page_content") or "")
    else:
        chunks.append(str(x))

# ---------- TOKENIZER ----------
enc = tiktoken.get_encoding(ENC_NAME)
def tok(s): return enc.encode(s)

# ---------- SENTENCE SPLITTING (regex, replace with spaCy if you like) ----------
SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9\"“(])')
sentences = [s for s in SENT_SPLIT_RE.split(orig_text) if s.strip()]

# Map sentence -> which chunks contain it
def find_spans(text, subs):
    # naive spans for demo; replace with better sentence char offsets if needed
    pos = 0
    out = []
    for s in subs:
        i = text.find(s, pos)
        if i == -1:
            i = text.find(s)  # fallback
        if i != -1:
            out.append((i, i+len(s)))
            pos = i + len(s)
        else:
            out.append((-1, -1))
    return out

sent_spans = find_spans(orig_text, sentences)

chunk_char_spans = []
cursor = 0
for c in chunks:
    start = orig_text.find(c, cursor)
    if start == -1:
        start = orig_text.find(c)  # fallback if deduped text differs
    end = start + len(c) if start != -1 else -1
    chunk_char_spans.append((start, end))
    if start != -1: cursor = end

# ---------- METRICS ----------
# Token sizes
chunk_tokens = [len(tok(c)) for c in chunks]
TBU = [t / TARGET_SIZE for t in chunk_tokens]
BD  = [abs(t - TARGET_SIZE) for t in chunk_tokens]

# Overlap Recall (exact) for the last OVERLAP_TOK
def overlap_recall(a, b, k=OVERLAP_TOK):
    ta, tb = tok(a), tok(b)
    if not ta or not tb or k == 0: return 0.0
    tail = ta[-k:] if len(ta) >= k else ta
    head = tb[:len(tail)]
    return 1.0 if tail == head else 0.0

OR_vals = []
for i in range(len(chunks)-1):
    OR_vals.append(overlap_recall(chunks[i], chunks[i+1]))

# Boundary Coherence: boundary falls on an allowed separator?
def boundary_on_sep(prev, nxt):
    if not prev or not nxt: return False
    left = prev[-1:]
    right = nxt[:1]
    # also allow known multi-char seps via trailing/leading check
    sep_hit = any(prev.endswith(sep) or nxt.startswith(sep) for sep in SEPARATORS if sep)
    # permit clean cut between alnum and sep
    return bool(sep_hit or (left and not left.isalnum()) or (right and not right.isalnum()))

BC_hits = []
for i in range(len(chunks)-1):
    BC_hits.append(boundary_on_sep(chunks[i], chunks[i+1]))

# Sentence Preservation & Fragmentation
def count_sentence_fragments(span, chunk_spans):
    s, e = span
    if s < 0: return 1  # unknown, treat as one
    hits = 0
    for (cs, ce) in chunk_spans:
        if cs < 0: continue
        # overlap if any intersection
        if max(cs, s) < min(ce, e):
            hits += 1
    return hits

frag_counts = [count_sentence_fragments(sp, chunk_char_spans) for sp in sent_spans]
broken = sum(1 for x in frag_counts if x > 1)
SPR = 1.0 - broken / max(1, len(frag_counts))
FI  = stats.mean(frag_counts) if frag_counts else 0

# Duplication Rate (approx): ratio of unique tokens across all chunks
all_tokens_flat = []
for c in chunks: all_tokens_flat.extend(tok(c))
unique = len(set(all_tokens_flat))
DR = 1 - (unique / max(1, len(all_tokens_flat)))

# Anchor Hit Rate: sample sentences as anchors
sample = sentences[:: max(1, len(sentences)//50 or 1)]  # ~50 anchors
def anchor_hit(anchor, chunks):
    return any(anchor in c for c in chunks)
AHR = sum(1 for a in sample if anchor_hit(a, chunks)) / max(1, len(sample))

# Local Continuity Similarity (Jaccard on token sets for adjacency)
def jaccard(a,b):
    A, B = set(tok(a)), set(tok(b))
    return len(A&B)/len(A|B) if A|B else 0.0

LCS = [jaccard(chunks[i], chunks[i+1]) for i in range(len(chunks)-1)]

# ---------- REPORT ----------
def describe(name, xs):
    if not xs: return f"{name}: n=0"
    return (f"{name}: n={len(xs)}, mean={stats.mean(xs):.3f}, "
            f"p50={stats.median(xs):.3f}, p90={sorted(xs)[int(0.9*len(xs))-1]:.3f}, "
            f"min={min(xs):.3f}, max={max(xs):.3f}")

print("=== STRUCTURE ===")
print(f"SPR (Sentence Preservation Rate): {SPR:.3%}")
print(f"FI (Fragmentation Index): {FI:.2f}")
print(f"BCS (Boundary Coherence Score): {sum(BC_hits)/max(1,len(BC_hits)):.3%}")

print("\n=== TOKEN BUDGET ===")
print(describe("TBU (token budget utilization)", TBU))
print(describe("BD  (boundary drift, abs tokens)", BD))
print(describe(f"OR@{OVERLAP_TOK} (overlap recall)", OR_vals))

print("\n=== REDUNDANCY & COVERAGE ===")
print(f"DR (Duplication Rate): {DR:.3%}")
print(f"AHR (Anchor Hit Rate): {AHR:.3%}")

print("\n=== CONTINUITY (adjacent similarity) ===")
print(describe("LCS (Jaccard on token sets)", LCS))
