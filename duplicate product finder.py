import os
import re
import pandas as pd
from rapidfuzz import fuzz
from tqdm import tqdm

# 1. Load the CSV
downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads', 'python3 canonical_finder_script.py  - 1 - Internal - HTML.csv')
df = pd.read_csv(downloads_path)

# 2. Define words and SKU patterns to clean
NOISE_WORDS = ['next-day-delivery', 'fully-installed', 'express-delivery', 'delivery', 'fast', 'shipping', 'free']

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Remove noise words
    for word in NOISE_WORDS:
        text = text.replace(word, "")
    # Remove standalone 5-6 digit SKU codes (e.g., '120985c') so fingerprinting focuses on the product name
    text = re.sub(r'\b\d{5,6}[a-z]?\b', '', text)
    return text.strip()

def get_numbers(text):
    # Only pull numbers that are 1-4 digits long (specs, sizes, tray counts) 
    # to avoid treating raw 6-digit SKUs as product specs
    nums = re.findall(r'\b\d{1,4}\b', text)
    return frozenset(nums)

# 3. Clean columns & create fingerprints
df['cleaned_Title 1'] = df['Title 1'].apply(clean_text)
df['cleaned_H1-1'] = df['H1-1'].apply(clean_text)
df['fingerprint'] = df['cleaned_Title 1'] + " " + df['cleaned_H1-1']
df['extracted_numbers'] = df['fingerprint'].apply(get_numbers)

# Helper function: Score a URL based on how "descriptive" it is vs a raw SKU
def url_quality_score(url):
    url_str = str(url).lower()
    score = 0
    # Penalize 'delivery' variants
    if 'delivery' in url_str:
        score -= 50
    # Penalize URLs that are just short raw SKUs (e.g., /120985c.html)
    if re.search(r'/[a-z0-9]{4,8}\.html', url_str):
        score -= 100
    # Reward long, hyphenated descriptive slugs
    hyphen_count = url_str.count('-')
    score += (hyphen_count * 10)
    # Prefer shorter overall lengths among equally descriptive URLs
    score -= len(url_str) * 0.1
    return score

results = []
processed_urls = set()

# 4. Process matches WITH PROGRESS BAR
for index, row in tqdm(df.iterrows(), total=len(df), desc="Matching URLs"):
    url = row['Address']
    current_fingerprint = row['fingerprint']
    current_numbers = row['extracted_numbers']
    
    if url in processed_urls:
        continue

    # Filter to identical specs/numbers first
    potential_matches = df[df['extracted_numbers'] == current_numbers]
    
    # Run RapidFuzz on filtered set
    group = potential_matches[potential_matches['fingerprint'].apply(lambda x: fuzz.ratio(current_fingerprint, x) > 85)]
    
    if not group.empty:
        urls_in_group = group['Address'].tolist()
        
        # Pick the canonical based on our quality score (highest score wins)
        canonical = max(urls_in_group, key=url_quality_score)
        
        for u in urls_in_group:
            results.append({'URL': u, 'Canonical': canonical})
            processed_urls.add(u)

# 5. Export
mapping_df = pd.DataFrame(results)
mapping_df.to_csv('canonical_mapping.csv', index=False)

print("\nSuccess! Refined canonical_mapping.csv file has been created.")
