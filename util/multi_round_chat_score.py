import argparse
import json
import requests


def calculate_coherence_scores(prompt_completion_pairs, url):
    scores = []
    for prompt, completion in prompt_completion_pairs:
        response = requests.post(f"{url}/analyze",
                                 json={
                                     "prompt": prompt,
                                     "completion": completion
                                 })
        if response.status_code == 200:
            result = response.json()
            scores.append(result["score"])
        else:
            scores.append(None)  # Handle error case
    return scores


def parse_jsonl_chat_log(log_file):
    prompt_completion_pairs = []
    with open(log_file, "r") as file:
        for line in file:
            data = json.loads(line)
            if data["interaction_type"] == "prompt":
                prompt = data["content"]
            elif data["interaction_type"] == "completion":
                completion = data["content"]
                prompt_completion_pairs.append((prompt, completion))
    return prompt_completion_pairs


def main():
    parser = argparse.ArgumentParser(
        description="Calculate prompt-to-completion coherence scores.")
    parser.add_argument("--url",
                        default="http://localhost:8100",
                        help="Prompt compliance service URL")
    parser.add_argument("--log",
                        required=True,
                        help="Path to the JSONL chat log file")
    args = parser.parse_args()

    prompt_completion_pairs = parse_jsonl_chat_log(args.log)
    coherence_scores = calculate_coherence_scores(prompt_completion_pairs,
                                                  args.url)

    # Print the coherence scores
    for i, score in enumerate(coherence_scores):
        print(f"Round {i+1}: Coherence Score = {score}")


if __name__ == "__main__":
    main()
