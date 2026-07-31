import streamlit as st
import pandas as pd
import re
from urllib.parse import urlparse
from rapidfuzz import fuzz

st.title("Luke's Canonical Finder🔎")
st.write("Upload your HTML crawl export CSV to map duplicate products to their best canonical URL.")

# 1. File Uploader UI Widget
uploaded_file = st.file_uploader("Choose a CSV file", type=["csv", "tsv", "txt"])

# Helper function to auto-detect column headers
def find_column(df, candidates):
    for col in df.columns:
        if col.strip().lower() in [c.lower() for c in candidates]:
            return col
    return None

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
    except Exception:
        df = pd.read_csv(uploaded_file)
        
    st.success(f"Successfully loaded {len(df)} rows!")

    # Column Auto-Detection
    default_url_col = find_column(df, ['Address', 'URL', 'Url', 'Page Address', 'Link'])
    default_title_col = find_column(df, ['Title 1', 'Title', 'Meta Title 1', 'Page Title', 'Meta Title', 'Title1'])
    default_h1_col = find_column(df, ['H1-1', 'H1', 'Heading 1', 'H1-1 Title', 'H1 1', 'H11'])
    default_desc_col = find_column(df, ['Meta Description 1', 'Meta Description', 'Description 1', 'Description', 'Meta Desc'])

    st.subheader("📋 Column Mapping")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        url_col = st.selectbox("URL Column", df.columns, index=df.columns.get_loc(default_url_col) if default_url_col in df.columns else 0)
    with col2:
        title_col = st.selectbox("Title Column", df.columns, index=df.columns.get_loc(default_title_col) if default_title_col in df.columns else 0)
    with col3:
        h1_col = st.selectbox("H1 Column (Optional)", ["None"] + list(df.columns), index=list(df.columns).index(default_h1_col)+1 if default_h1_col in df.columns else 0)
    with col4:
        desc_col = st.selectbox("Meta Desc (Optional)", ["None"] + list(df.columns), index=list(df.columns).index(default_desc_col)+1 if default_desc_col in df.columns else 0)

    st.subheader("⚙️ SEO & Matching Preferences")
    
    col_a, col_b = st.columns(2)
    with col_a:
        similarity_threshold = st.slider("Fuzzy Matching Similarity Threshold (%)", min_value=70, max_value=100, value=95, step=1)
    
    with col_b:
        default_noise = "next-day-delivery, fully-installed, express-delivery, delivery, fast, shipping, free, in-stock, sale, express"
        noise_input = st.text_input("Boilerplate/Noise words to ignore:", value=default_noise)

    STRIP_KEYWORDS = ["next day delivery", "fully installed", "next-day-delivery", "fully-installed"]

    # 2. Strict SEO Scoring Hierarchy Engine
    def url_quality_score(url):
        url_str = str(url).lower()
        parsed = urlparse(url_str)
        path = parsed.path
        query = parsed.query
        
        score = 1000  # Base starting score
        
        # Rule 1: Query Parameters (-1000)
        if query:
            score -= 1000
            
        # Rule 2: Pure Numeric SKU URLs (-600)
        filename = path.rstrip('/').split('/')[-1] if path else ""
        name_no_ext = filename.split('.')[0]
        if name_no_ext.isdigit() and len(name_no_ext) > 0:
            score -= 600

        # Rule 3: Paginated Path Slugs (-400)
        if re.search(r'/\d+/\d+(/|$)', path):
            score -= 400

        # Rule 4: Promo Keywords (-300)
        if re.search(r'/(sale|clearance|express)(/|-|_|$)', path):
            score -= 300

        # Rule 5: Deep Folder Slashes (-25 per slash)
        slash_count = len([seg for seg in path.split('/') if seg])
        score -= (slash_count * 25)

        # Rule 6: Path Length Deduction (-1 per char)
        score -= len(path)
        
        return score

    # 3. Process Button with Live Feedback
    if st.button("Run Canonical Matching"):
        with st.spinner("Analyzing CSV & running canonical engine... Please wait!"):
            NOISE_WORDS = [word.strip().lower() for word in noise_input.split(",") if word.strip()]

            def clean_text(text):
                if not isinstance(text, str):
                    return ""
                text = text.lower()
                text = re.sub(r'[™®©]', '', text)
                
                for kw in STRIP_KEYWORDS:
                    text = re.sub(re.escape(kw.lower()), "", text)
                    
                for word in NOISE_WORDS:
                    text = re.sub(r'\b' + re.escape(word) + r'\b', '', text)
                    
                return re.sub(r'\s+', ' ', text).strip()

            def get_numbers(row):
                fingerprint = str(row['fingerprint'])
                url_path = str(row['Address_internal'])
                combined = f"{fingerprint} {url_path}"
                return frozenset(re.findall(r'\b\d{1,4}\b', combined))

            def has_conflict(row1, row2):
                text1 = f"{row1['fingerprint']} {row1['Address_internal']}".lower()
                text2 = f"{row2['fingerprint']} {row2['Address_internal']}".lower()

                colors = ['white', 'black', 'grey', 'gray', 'silver', 'beech', 'oak', 'maple', 'walnut', 'ash', 'blue', 'red', 'green', 'yellow', 'purple', 'orange']
                col1 = {c for c in colors if re.search(r'\b' + c + r'\b', text1)}
                col2 = {c for c in colors if re.search(r'\b' + c + r'\b', text2)}
                if col1 != col2:
                    return True

                shapes = {}
                for text, key in [(text1, 's1'), (text2, 's2')]:
                    tags = set()
                    if any(term in text for term in ['semi-circular', 'semi circular', 'semicircular']):
                        tags.add('semi_circ')
                    elif any(term in text for term in ['circular', 'circle', 'round']):
                        tags.add('circ')
                    if any(term in text for term in ['rectangular', 'rectangle']):
                        tags.add('rect')
                    if 'square' in text:
                        tags.add('sq')
                    shapes[key] = tags

                if shapes['s1'] and shapes['s2'] and shapes['s1'] != shapes['s2']:
                    return True

                return False

            # Internal Standardization
            df['Address_internal'] = df[url_col]
            fingerprint_series = df[title_col].apply(clean_text)
            
            if h1_col != "None" and h1_col in df.columns:
                fingerprint_series = fingerprint_series + " " + df[h1_col].apply(clean_text)
                
            if desc_col != "None" and desc_col in df.columns:
                fingerprint_series = fingerprint_series + " " + df[desc_col].apply(clean_text)

            df['fingerprint'] = fingerprint_series
            df['extracted_numbers'] = df.apply(get_numbers, axis=1)

            results = []
            processed_urls = set()
            total_rows = len(df)
            
            # Placeholders for live visual updates
            status_text = st.empty()
            progress_bar = st.progress(0)

            for index, row in df.iterrows():
                url = row['Address_internal']
                current_fingerprint = row['fingerprint']
                current_numbers = row['extracted_numbers']
                
                # Live visual UI updates
                pct_complete = int(((index + 1) / total_rows) * 100)
                status_text.text(f" Processing row {index + 1} of {total_rows} ({pct_complete}% complete)...")
                progress_bar.progress((index + 1) / total_rows)

                if url in processed_urls:
                    continue

                potential_matches = df[df['extracted_numbers'] == current_numbers]
                matched_rows = potential_matches[
                    potential_matches['fingerprint'].apply(
                        lambda x: fuzz.token_set_ratio(current_fingerprint, x) >= similarity_threshold
                    )
                ]

                valid_urls = []
                for _, m_row in matched_rows.iterrows():
                    if not has_conflict(row, m_row):
                        valid_urls.append(m_row['Address_internal'])

                if valid_urls:
                    canonical = max(valid_urls, key=url_quality_score)
                    canonical_score = url_quality_score(canonical)
                    for u in valid_urls:
                        results.append({
                            'URL': u, 
                            'Canonical': canonical,
                            'Is Self-Referencing': 'Yes' if u == canonical else 'No',
                            'Canonical Score': canonical_score
                        })
                        processed_urls.add(u)
                else:
                    results.append({
                        'URL': url,
                        'Canonical': url,
                        'Is Self-Referencing': 'Yes',
                        'Canonical Score': url_quality_score(url)
                    })
                    processed_urls.add(url)

            # Clear status text when done
            status_text.empty()
            mapping_df = pd.DataFrame(results)
            
            st.success("Yippeee! Canonical Matching Complete.")
            
            csv_data = mapping_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Canonical Mapping CSV",
                data=csv_data,
                file_name="canonical_mapping.csv",
                mime="text/csv"
            )
