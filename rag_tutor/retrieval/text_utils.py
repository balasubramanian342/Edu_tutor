"""
text_utils.py

Shared tokenizer for BM25 indexing and querying.

IMPORTANT: build_index.py and hybrid_retriever.py must use the exact
same tokenization, or BM25 scores become meaningless (a token that's
split differently at index time vs query time will never match, even
if the words are identical). Both import `tokenize` from here instead
of each doing their own `.lower().split()`.

This fixes a real bug from the naive version: `"recursion:".split()`
produces the token "recursion:" (with the colon attached), which will
never match a query token "recursion". Using a \\w+ regex strips
punctuation so "Recursion:", "(recursion)", and "recursion." all
tokenize to the same "recursion".

Known limitation (documented, not fixed here to avoid adding an NLP
dependency): this does not stem/lemmatize, so "stack" and "stacks" are
still different tokens. Dense retrieval (embeddings) already covers
this case semantically, which is exactly why the system uses hybrid
retrieval rather than BM25 alone — if you want to improve BM25
specifically, adding a lightweight stemmer (e.g. nltk's PorterStemmer)
to `tokenize()` here is the place to do it.
"""

import re

_TOKEN_RE = re.compile(r"\w+")

# BM25 has no notion of word importance on its own — without filtering,
# a short/generic query like "what is a variable" scores chunks mostly on
# how often they contain "is"/"a"/"what" rather than the one word that
# actually matters ("variable"). That produced real, misleading results:
# a query about variables matched a completely unrelated Stack chunk with
# a *higher* score than anything else, purely because it happened to
# contain "is" and "a" more often. This list is intentionally small (just
# the highest-frequency function words that carry no topical meaning) —
# removing too aggressively risks stripping words that matter in a CS
# context (e.g. "or", "if", "then" can be meaningful in code-adjacent text).
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "of", "to", "in", "on", "at", "for", "with", "as", "by", "it", "its",
    "do", "does", "did", "can", "could", "will", "would", "should",
    "and", "but", "so", "i", "you", "your", "me", "my",
}


def tokenize(text: str) -> list:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS] or tokens
