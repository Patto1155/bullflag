import os
import csv
import openai
from typing import List, Dict

# Set your OpenAI API key here or via environment variable
OPENAI_API_KEY = os.getenv('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')
openai.api_key = OPENAI_API_KEY

CHARTS_DIR = 'charts'
LABELS_FILE = 'labels.csv'
RESULTS_FILE = 'classification_results.csv'

PROMPT = """
You are a trading expert. Does this candlestick chart contain a bull flag pattern? Respond with 'bull_flag' or 'not_bull_flag', and explain your reasoning in 1-2 sentences.
"""

def load_labels(labels_file: str) -> Dict[str, str]:
    labels = {}
    with open(labels_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels[row['filename']] = row['label']
    return labels

def classify_image_with_gpt4o(image_path: str) -> (str, str):
    with open(image_path, 'rb') as img_file:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a trading expert."},
                {"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image", "image": img_file.read()}
                ]}
            ],
            max_tokens=256,
        )
    content = response.choices[0].message.content.strip()
    if 'bull_flag' in content.lower():
        pred = 'bull_flag'
    else:
        pred = 'not_bull_flag'
    return pred, content

def main():
    labels = load_labels(LABELS_FILE)
    results = []
    for filename in os.listdir(CHARTS_DIR):
        if filename.endswith('.png'):
            filepath = os.path.join(CHARTS_DIR, filename)
            print(f"Classifying {filename}...")
            pred, reasoning = classify_image_with_gpt4o(filepath)
            results.append({
                'filename': filename,
                'ground_truth': labels.get(filename, ''),
                'prediction': pred,
                'reasoning': reasoning
            })
    # Save results
    with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'ground_truth', 'prediction', 'reasoning'])
        writer.writeheader()
        writer.writerows(results)
    print(f"Results saved to {RESULTS_FILE}")

if __name__ == '__main__':
    main()
