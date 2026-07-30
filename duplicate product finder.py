import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz

st.title("Luke's Canonical Finder Tool 🔎")
st.write("Upload your HTML crawl export CSV to map duplicate products to their best canonical URL.")

# 1. File Uploader UI Widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# 2. Dynamic Noise Words Input Box
default_noise = "next-day-delivery, fully-installed, express-delivery, delivery, fast, shipping, free, in-stock, sale"
noise_input = st.text_input(
    "Boilerplate/Noise words to ignore (separated by commas):", 
    value=default_noise,
    help="Add words that appear in titles/H1s that should be ignored during product matching."
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully!")
    
    # 3. Process Button
    if st.button("Run Canonical Matching"):
        NOISE_WORDS = [word.strip().lower() for word in noise_input.split(",") if word.strip()]

        def clean_text(text):
            if not isinstance(text, str):
                return ""
            text = text.lower()
            for word in NOISE_WORDS:
                text = text.replace(word, "")
            text = re.sub(r'\b\d{5,6}[a-z]?\b', '', text)
            return text.strip()

        # Extract 1-4 digit numbers from BOTH Title/H1 fingerprint and the URL address path
        def get_numbers(row):
            fingerprint = str(row['fingerprint'])
            url_path = str(row['Address'])
            combined = f"{fingerprint} {url_path}"
            return frozenset(re.findall(r'\b\d{1,4}\b', combined))

        def url_quality_score(url):
            url_str = str(url).lower()
            score = 0
            if 'delivery' in url_str:
                score -= 50
            if re.search(r'/[a-z0-9]{4,8}\.html', url_str):
                score -= 100
            score += (url_str.count('-') * 10)
            score -= len(url_str) * 0.1
            return score

        # Prevent cross-category matches (e.g. desks vs chairs)
        def has_category_conflict(url1, url2):
            u1, u2 = str(url1).lower(), str(url2).lower()
            categories = ['chair', 'desk', 'table', 'storage', 'screen', 'bench', 'tray']
            u1_cats = {c for c in categories if c in u1}
            u2_cats = {c for c in categories if c in u2}
            if u1_cats and u2_cats and u1_cats != u2_cats:
                return True
            return False

        df['cleaned_Title 1'] = df['Title 1'].apply(clean_text)
        df['cleaned_H1-1'] = df['H1-1'].apply(clean_text)
        df['fingerprint'] = df['cleaned_Title 1'] + " " + df['cleaned_H1-1']
        df['extracted_numbers'] = df.apply(get_numbers, axis=1)

        results = []
        processed_urls = set()

        # 4. Streamlit Web Progress Bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_rows = len(df)

        for index, row in df.iterrows():
            url = row['Address']
            current_fingerprint = row['fingerprint']
            current_numbers = row['extracted_numbers']
            
            progress_bar.progress((index + 1) / total_rows)
            status_text.text(f"Processing row {index + 1} of {total_rows}...")

            if url in processed_urls:
                continue

            # GUARDRAIL 1: Skip matching if title/H1 fingerprint is too short/empty
            if len(current_fingerprint.strip()) < 8:
                results.append({
                    'URL': url,
                    'Canonical': url,
                    'Is Self-Referencing': 'Yes'
                })
                processed_urls.add(url)
                continue

            potential_matches = df[df['extracted_numbers'] == current_numbers]
            
            # Fuzzy match on fingerprint
            matched_rows = potential_matches[
                potential_matches['fingerprint'].apply(lambda x: fuzz.ratio(current_fingerprint, x) > 85)
            ]
            
            # GUARDRAIL 2: Filter out category conflicts (e.g., desks matching chairs)
            valid_urls = [
                m_url for m_url in matched_rows['Address'].tolist()
                if not has_category_conflict(url, m_url)
            ]

            if valid_urls:
                canonical = max(valid_urls, key=url_quality_score)
                for u in valid_urls:
                    is_self_ref = "Yes" if u == canonical else "No"
                    results.append({
                        'URL': u, 
                        'Canonical': canonical,
                        'Is Self-Referencing': is_self_ref
                    })
                    processed_urls.add(u)
            else:
                results.append({
                    'URL': url,
                    'Canonical': url,
                    'Is Self-Referencing': 'Yes'
                })
                processed_urls.add(url)

        mapping_df = pd.DataFrame(results)
        
        st.success("Yippeee! Matching Is Complete.")
        
        # 5. Download Button & Reminder
        st.caption("⚠️ Always double-check the output before sending over to a client.")
        csv_data = mapping_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Canonical Mapping CSV",
            data=csv_data,
            file_name="canonical_mapping.csv",
            mime="text/csv"
        )
