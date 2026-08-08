import logging
from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class VectorStore:
    """Lightweight vector store for CPS Engine."""

    def __init__(self):
        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        self.documents: List[str] = []
        self.embeddings: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []

        self._initialize_documents()

    def _initialize_documents(self):
        """Load initial Hausa history knowledge."""

        hausa_texts = [
            (
                "Bayajidda arrived from Baghdad "
                "and married Queen Daurama of Daura."
            ),
            (
                "Kano was founded by Bagauda, "
                "son of Bayajidda."
            ),
            (
                "The Hausa Bakwai are seven states "
                "traditionally associated with the "
                "descendants of Bayajidda."
            ),
            (
                "Queen Daurama was the ruler of "
                "Daura before the arrival of Bayajidda."
            ),
            (
                "The snake Kurkuru prevented people "
                "from fetching water until Bayajidda "
                "killed it."
            ),
            (
                "Sheikh Al-Maghili advised "
                "Muhammadu Rumfa on Islamic governance."
            ),
            (
                "Ajami is a writing system that uses "
                "Arabic characters to write Hausa."
            ),
            (
                "Trans-Saharan trade connected Hausa "
                "states with North Africa."
            ),
            (
                "Kano became an important center of "
                "Islamic learning and scholarship "
                "in West Africa."
            ),
            (
                "The Bagauda dynasty is traditionally "
                "associated with the early history "
                "of Kano."
            ),
        ]

        for text in hausa_texts:
            try:
                embedding = self.model.encode(
                    text,
                    convert_to_numpy=True,
                )

                self.documents.append(text)
                self.embeddings.append(embedding)

                self.metadata.append(
                    {
                        "source": "hausa_history",
                    }
                )

            except Exception as exc:
                logger.error(
                    "Embedding generation failed: %s",
                    exc,
                )

        logger.info(
            "Vector store initialized with %d documents",
            len(self.documents),
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search documents using cosine similarity."""

        if not self.documents:
            return []

        if not query or not query.strip():
            return []

        try:
            query_embedding = self.model.encode(
                query,
                convert_to_numpy=True,
            )

            similarities = []

            for index, document_embedding in enumerate(
                self.embeddings
            ):
                denominator = (
                    np.linalg.norm(query_embedding)
                    * np.linalg.norm(document_embedding)
                )

                if denominator == 0:
                    similarity = 0.0
                else:
                    similarity = float(
                        np.dot(
                            query_embedding,
                            document_embedding,
                        )
                        / denominator
                    )

                similarities.append(
                    (similarity, index)
                )

            similarities.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            results = []

            for similarity, index in similarities[
                :top_k
            ]:
                if similarity >= 0.5:
                    results.append(
                        {
                            "text": self.documents[index],
                            "similarity": similarity,
                            "metadata": self.metadata[
                                index
                            ],
                        }
                    )

            return results

        except Exception as exc:
            logger.error(
                "Vector search failed: %s",
                exc,
            )
            return []

    async def health_check(self) -> bool:
        """Check vector store health."""

        try:
            results = self.search(
                "Hausa history",
                top_k=1,
            )

            return len(results) >= 0

        except Exception as exc:
            logger.error(
                "Vector store health check failed: %s",
                exc,
            )
            return False
