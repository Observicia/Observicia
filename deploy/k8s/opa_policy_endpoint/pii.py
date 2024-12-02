from fastapi import FastAPI
from presidio_analyzer import AnalyzerEngine, RecognizerResult

analyzer = AnalyzerEngine()

app = FastAPI()

PII_PATTERNS = {
    "PERSON": "Name of a person",
    "PHONE_NUMBER": "Phone number pattern",
    "EMAIL_ADDRESS": "Email address pattern"
}

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    text: str


@app.post("/analyze")
def analyze_text(request: AnalyzeRequest):
    text = request.text
    print(f"Analyzing text: {text}")
    results = analyzer.analyze(text=text,
                               entities=PII_PATTERNS.keys(),
                               language="en")
    return [{
        "entity_type": result.entity_type,
        "start": result.start,
        "end": result.end,
        "score": result.score,
    } for result in results]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
