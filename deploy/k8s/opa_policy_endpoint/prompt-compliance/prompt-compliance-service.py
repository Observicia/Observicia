from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F

app = FastAPI()

# model and tokenizer for semantic similarity computation
tokenizer = AutoTokenizer.from_pretrained(
    'sentence-transformers/all-MiniLM-L6-v2')
model = AutoModel.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')


class AnalyzeRequest(BaseModel):
    prompt: str
    completion: str


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(
        token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9)


def get_embeddings(texts):
    encoded_input = tokenizer(texts,
                              padding=True,
                              truncation=True,
                              return_tensors='pt')
    with torch.no_grad():
        model_output = model(**encoded_input)
    return mean_pooling(model_output, encoded_input['attention_mask'])


def compute_similarity(prompt: str, completion: str) -> float:
    embeddings = get_embeddings([prompt, completion])

    # compute cosine similarity
    similarity = F.cosine_similarity(embeddings[0].unsqueeze(0),
                                     embeddings[1].unsqueeze(0))

    return float(similarity)


@app.post("/analyze")
async def analyze_prompt_compliance(request: AnalyzeRequest):
    try:
        print(f"Analyzing prompt: {request.prompt}")
        print(f"Analyzing completion: {request.completion}")
        # get semantic similarity between prompt and completion
        score = compute_similarity(request.prompt, request.completion)
        print(f"Score: {score}")
        return {
            "score": score,
            "metadata": {
                "method": "semantic_similarity",
                "model": "all-MiniLM-L6-v2"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
