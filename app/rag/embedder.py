from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class Embedder:
    vectorizer: TfidfVectorizer

    @classmethod
    def fit(cls, texts: Sequence[str]) -> tuple["Embedder", np.ndarray]:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, norm="l2")
        matrix = vectorizer.fit_transform(texts)
        vectors = matrix.toarray().astype("float32")
        return cls(vectorizer=vectorizer), vectors

    def embed_query(self, text: str) -> np.ndarray:
        vec = self.vectorizer.transform([text]).toarray().astype("float32")
        return vec
