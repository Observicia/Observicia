import os
import argparse
from typing import List, Dict, Tuple
import numpy as np
import faiss
import openai
from sentence_transformers import SentenceTransformer
from observicia import init

# Initialize Observicia
init()

import warnings

warnings.filterwarnings("ignore")


class PatientRAGSystem:

    def __init__(self, similarity_threshold: float = 0.5):
        """
        Initialize the RAG system with similarity threshold.

        Args:
            similarity_threshold (float): Minimum similarity score (0-1) for retrieved documents.
                                        Higher values mean stricter matching.
        """
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384  # Model embedding dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.similarity_threshold = similarity_threshold
        self.client = openai.OpenAI()

    def add_patient_data(self, patient_records: List[Dict[str, str]]):
        """Add patient records to the RAG system"""
        for record in patient_records:
            text = f"Patient {record['name']}: {record['info']}"
            embedding = self.model.encode([text])[0]
            self.index.add(np.array([embedding]).astype('float32'))
            self.documents.append(text)

    def _get_relevant_documents(self,
                                query: str,
                                k: int = 3) -> List[Tuple[str, float]]:
        """
        Get relevant documents with their similarity scores.

        Args:
            query (str): Query text
            k (int): Maximum number of documents to retrieve

        Returns:
            List[Tuple[str, float]]: List of (document, similarity_score) pairs
        """
        # Get query embedding
        query_embedding = self.model.encode([query])[0]

        # Search similar documents - returns distances and indices
        distances, indices = self.index.search(
            np.array([query_embedding]).astype('float32'), k)

        # Convert L2 distances to similarity scores (0-1 scale)
        max_l2_distance = float(
            np.sqrt(2) *
            2)  # Maximum possible L2 distance for normalized vectors
        similarity_scores = 1 - (distances[0] / max_l2_distance)

        # Filter and return documents with scores
        relevant_docs = []
        for idx, score in zip(indices[0], similarity_scores):
            if score >= self.similarity_threshold:
                relevant_docs.append((self.documents[idx], float(score)))

        return relevant_docs

    async def get_answer(self, query: str, k: int = 3) -> Dict[str, any]:
        """
        Get answer using RAG with similarity score filtering.
        Falls back to direct LLM query if no relevant documents found.

        Args:
            query (str): User query
            k (int): Maximum number of documents to retrieve

        Returns:
            Dict[str, any]: Dictionary containing answer and retrieval metadata
        """
        # Get relevant documents with scores
        relevant_docs = self._get_relevant_documents(query, k)

        if relevant_docs:
            used_docs, scores = zip(*relevant_docs)
            context = "\n".join(used_docs)
            messages = [{
                "role":
                "system",
                "content":
                "You are a helpful medical assistant. Use the provided context to answer questions about patients."
            }, {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}"
            }]
        else:
            messages = [{
                "role":
                "system",
                "content":
                "You are a helpful medical assistant. If you don't have specific information, provide a general response."
            }, {
                "role": "user",
                "content": query
            }]

        # Get completion
        response = self.client.chat.completions.create(model="gpt-3.5-turbo",
                                                       messages=messages,
                                                       max_tokens=150)

        return {
            "answer": response.choices[0].message.content,
            "context_used": list(used_docs) if relevant_docs else [],
            "similarity_scores": list(scores) if relevant_docs else [],
            "used_context": bool(relevant_docs)
        }


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Patient RAG System with similarity threshold')
    parser.add_argument(
        '--similarity-threshold',
        type=float,
        default=0.6,
        help=
        'Minimum similarity score (0-1) for retrieved documents. Default: 0.6')
    parser.add_argument(
        '--max-docs',
        type=int,
        default=3,
        help='Maximum number of documents to retrieve. Default: 3')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Show detailed retrieval information')

    args = parser.parse_args()

    if not 0 <= args.similarity_threshold <= 1:
        parser.error("Similarity threshold must be between 0 and 1")

    print(f"Using similarity threshold: {args.similarity_threshold}")
    print(f"Maximum documents to retrieve: {args.max_docs}")

    # Sample patient data
    patients = [{
        "name": "John Smith",
        "info": "Age 45, Diabetes Type 2, Last visit: 2024-01-15"
    }, {
        "name": "Alice Johnson",
        "info": "Age 32, Asthma, Contact: 555-0123"
    }, {
        "name": "Bob Wilson",
        "info": "Age 58, Hypertension, Email: bob@email.com"
    }]

    # Initialize RAG with command line arguments
    rag = PatientRAGSystem(similarity_threshold=args.similarity_threshold)
    rag.add_patient_data(patients)

    # Test queries
    queries = [
        "What conditions does John have?",
        "Tell me about Alice's contact information",
        "What is Bob's age?",
        "What was John's last visit date?",
        "How many patients do we have?",
        "How many patients do we have? Don't show their personal information, including names",
        "What is the symptom of Hypertension?",
    ]

    for query in queries:
        try:
            result = await rag.get_answer(query, k=args.max_docs)
            print(f"\nQ: {query}")
            print(f"A: {result['answer']}")

            if args.verbose:
                print("\nContext used:")
                for doc, score in zip(result['context_used'],
                                      result['similarity_scores']):
                    print(f"- Score {score:.3f}: {doc}")
            else:
                if result['context_used']:
                    print(
                        f"\nUsed {len(result['context_used'])} documents with scores: "
                        + ", ".join(f"{score:.3f}"
                                    for score in result['similarity_scores']))

        except ValueError as e:
            print(f"\nQ: {query}")
            print(f"\033[91mPolicy violation: {str(e)}\033[0m")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
