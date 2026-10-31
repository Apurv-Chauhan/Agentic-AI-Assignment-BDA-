import re
import math
from typing import List, Dict, Any, Tuple
from pathlib import Path
from src.config import POLICY_FILE

class PolicyRetriever:
    """
    RAG retriever that chunks the student handbook and retrieves only
    the most relevant policy sections based on BM25-style lexical ranking.
    Avoids dumping the entire handbook into the context window.
    """
    def __init__(self, policy_path: Path = POLICY_FILE):
        self.policy_path = policy_path
        self.chunks: List[Dict[str, Any]] = []
        self._load_and_chunk()

    def _tokenize(self, text: str) -> List[str]:
        # Lowercase, strip punctuation, split into tokens
        tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
            "of", "with", "by", "from", "up", "about", "into", "over", "after",
            "is", "am", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "do", "does", "did", "can", "could", "should", "would", "may",
            "what", "which", "who", "when", "where", "why", "how", "all", "any",
            "both", "each", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very", "my", "your"
        }
        return [t for t in tokens if t not in stopwords]

    def _load_and_chunk(self):
        if not self.policy_path.exists():
            return

        with open(self.policy_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Split markdown text by ### Section or ## Section headers
        sections = re.split(r"(?=(?:###?\s*Section\s*\d+))", raw_text)
        
        chunk_idx = 1
        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean or len(sec_clean) < 30:
                continue

            # Extract header if present
            lines = sec_clean.split("\n")
            header_match = re.match(r"###?\s*(Section\s*\d+:[^\n]+)", lines[0])
            if header_match:
                title = header_match.group(1).strip()
            else:
                title = f"Policy Section {chunk_idx}"

            chunk_id = f"POLICY-SEC-{chunk_idx}"
            tokens = self._tokenize(sec_clean)

            self.chunks.append({
                "chunk_id": chunk_id,
                "title": title,
                "content": sec_clean,
                "tokens": tokens,
                "token_count": len(tokens)
            })
            chunk_idx += 1

    def retrieve(self, query: str, top_k: int = 2, min_score: float = 0.8) -> List[Dict[str, Any]]:
        """
        Score each policy chunk against the query using BM25 / TF-IDF scoring.
        Returns top-k matching chunks exceeding min_score.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        # Corpus statistics
        num_docs = len(self.chunks)
        avg_doc_len = sum(c["token_count"] for c in self.chunks) / max(1, num_docs)
        
        # Calculate doc frequencies for query tokens
        scores: List[Tuple[float, Dict[str, Any]]] = []
        k1 = 1.5
        b = 0.75

        for chunk in self.chunks:
            score = 0.0
            doc_len = chunk["token_count"]
            doc_tokens = chunk["tokens"]

            # Token frequencies in this chunk
            tf_dict: Dict[str, int] = {}
            for t in doc_tokens:
                tf_dict[t] = tf_dict.get(t, 0) + 1

            for q_token in set(query_tokens):
                if q_token in tf_dict:
                    # Document frequency
                    df = sum(1 for c in self.chunks if q_token in c["tokens"])
                    # IDF with smoothing
                    idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                    tf = tf_dict[q_token]
                    
                    term_score = idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len))))
                    score += term_score

            # Boost exact keyword matches in titles
            for q_token in query_tokens:
                if q_token in chunk["title"].lower():
                    score += 1.5

            if score >= min_score:
                scores.append((score, chunk))

        # Sort descending by score
        scores.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for s, chunk in scores[:top_k]:
            results.append({
                "chunk_id": chunk["chunk_id"],
                "title": chunk["title"],
                "content": chunk["content"],
                "relevance_score": round(s, 2)
            })
        return results
