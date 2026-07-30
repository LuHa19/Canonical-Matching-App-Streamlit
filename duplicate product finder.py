import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz

st.title("SEO Canonical Finder Tool 🚀")
st.write("Upload your HTML crawl export CSV to map duplicate products to their best canonical URL.")

# 1. File Uploader UI Widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully!")
    
    # 2. Process Button
    if st.button("Run Canonical Matching"):
        NOISE_WORDS = ['next-day-delivery', 'fully-installed', 'express-delivery', 'delivery', 'fast', 'shipping', 'free']

        def clean_text(text):
            if not isinstance(text, str):
                return ""
            text = text.lower()
            for word in NOISE_WORDS:
                text = text.replace(word, "")
            text = re.sub(r'\b\d{5,6}[a-z]?\b', '', text)
            return text.strip()

        def get_numbers(text):
            return frozenset(re.findall(r'\b\d{1,4}\b', text))

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

        df['cleaned_Title 1'] = df['Title 1'].apply(clean_text)
        df['cleaned_H1-1'] = df['H1-1'].apply(clean_text)
        df['fingerprint'] = df['cleaned_Title 1'] + " " + df['cleaned_H1-1']
        df['extracted_numbers'] = df['fingerprint'].apply(get_numbers)

        results = []
        processed_urls = set()

        # 3. Native Streamlit Web Progress Bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_rows = len(df)

        for index, row in df.iterrows():
            url = row['Address']
            current_fingerprint = row['fingerprint']
            current_numbers = row['extracted_numbers']
            
            # Update web progress bar
            progress_bar.progress((index + 1) / total_rows)
            status_text.text(f"Processing row {index + 1} of {total_rows}...")

            if url in processed_urls:
                continue

            potential_matches = df[df['extracted_numbers'] == current_numbers]
            group = potential_matches[potential_matches['fingerprint'].apply(lambda x: fuzz.ratio(current_fingerprint, x) > 85)]
            
            if not group.empty:
                urls_in_group = group['Address'].tolist()
                canonical = max(urls_in_group, key=url_quality_score)
                for u in urls_in_group:
                    results.append({'URL': u, 'Canonical': canonical})
                    processed_urls.add(u)

        mapping_df = pd.DataFrame(results)
        
        st.success("Matching Complete!")
        
        # 4. Download Button
        csv_data = mapping_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Canonical Mapping CSV",
            data=csv_data,
            file_name="canonical_mapping.csv",
            mime="text/csv"
        )
