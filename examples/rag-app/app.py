import os
from typing import List, Dict
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

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384  # Model embedding dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.client = openai.OpenAI()

    def add_patient_data(self, patient_records: List[Dict[str, str]]):
        """Add patient records to the RAG system"""
        for record in patient_records:
            text = f"Patient {record['name']}: {record['info']}"
            embedding = self.model.encode([text])[0]
            self.index.add(np.array([embedding]).astype('float32'))
            self.documents.append(text)

    async def get_answer(self, query: str, k: int = 3) -> str:
        """Get answer using RAG and OpenAI"""
        # Get query embedding
        query_embedding = self.model.encode([query])[0]

        # Search similar documents
        D, I = self.index.search(
            np.array([query_embedding]).astype('float32'), k)
        context = "\n".join(self.documents[i] for i in I[0])

        # Create prompt with context
        messages = [{
            "role":
            "system",
            "content":
            "You are a helpful medical assistant. Use the provided context to answer questions about patients."
        }, {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {query}"
        }]

        # Get completion
        response = self.client.chat.completions.create(model="gpt-3.5-turbo",
                                                       messages=messages,
                                                       max_tokens=150)

        return response.choices[0].message.content


# Sample usage
async def main():
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

    rag = PatientRAGSystem()
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
            answer = await rag.get_answer(query)
            print(f"\nQ: {query}")
            print(f"A: {answer}")
        except ValueError as e:
            print(f"\nQ: {query}")
            print(f"\033[91mPolicy violation: {str(e)}\033[0m")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
