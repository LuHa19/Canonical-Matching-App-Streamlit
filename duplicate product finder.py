import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz

st.title("Luke's Canonical Finder Tool 🔎")
st.write("Upload your HTML crawl export CSV to map duplicate products to their best canonical URL.")

# 1. File Uploader UI Widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# Helper function to auto-detect column headers
def find_column(df, candidates):
    for col in df.columns:
        if col.strip().lower() in [c.lower() for c in candidates]:
            return col
    return None

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully!")
    
    # Auto-detect standard columns or let user select them
    default_url_col = find_column(df, ['Address', 'URL', 'Url', 'Page Address', 'Link'])
    default_title_col = find_column(df, ['Title 1', 'Title', 'Meta Title 1', 'Page Title', 'Meta Title', 'Title1'])
    default_h1_col = find_column(df, ['H1-1', 'H1', 'Heading 1', 'H1-1 Title', 'H1 1', 'H11'])

    st.subheader("📋 Column Mapping")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        url_col = st.selectbox("URL Column", df.columns, index=df.columns.get_loc(default_url_col) if default_url_col in df.columns else 0)
    with col2:
        title_col = st.selectbox("Title Column", df.columns, index=df.columns.get_loc(default_title_col) if default_title_col in df.columns else 0)
    with col3:
        h1_col = st.selectbox("H1 Column (Optional)", ["None"] + list(df.columns), index=list(df.columns).index(default_h1_col)+1 if default_h1_col in df.columns else 0)

    # 2. Interactive Control Settings
    default_noise = "next-day-delivery, fully-installed, express-delivery, delivery, fast, shipping, free, in-stock, sale, express"
    noise_input = st.text_input(
        "Boilerplate/Noise words to ignore (separated by commas):", 
        value=default_noise,
        help="Add words that appear in titles/H1s that should be ignored during product matching."
    )

    similarity_threshold = st.slider(
        "Fuzzy Matching Similarity Threshold (%)",
        min_value=70,
        max_value=100,
        value=95,
        step=1,
        help="Higher values require tighter title alignment. Token-set matching handles word order differences."
    )

    # 3. Process Button
    if st.button("Run Canonical Matching"):
        NOISE_WORDS = [word.strip().lower() for word in noise_input.split(",") if word.strip()]

        def clean_text(text):
            if not isinstance(text, str):
                return ""
            text = text.lower()
            text = re.sub(r'[™®©]', '', text)
            for word in NOISE_WORDS:
                text = re.sub(r'\b' + re.escape(word) + r'\b', '', text)
            return re.sub(r'\s+', ' ', text).strip()

        # Extract 1-4 digit spec numbers (e.g. 11, 14 years or 1200mm)
        def get_numbers(row):
            fingerprint = str(row['fingerprint'])
            url_path = str(row['Address_internal'])
            combined = f"{fingerprint} {url_path}"
            return frozenset(re.findall(r'\b\d{1,4}\b', combined))

        # URL SEO Quality Score
        def url_quality_score(url):
            url_str = str(url).lower()
            score = 0
            if re.search(r'/[0-9]{4,8}[a-z]?\.html', url_str):
                score -= 500
            if 'delivery' in url_str or re.search(r'/[0-9]{1,3}$', url_str):
                score -= 100
            score += (url_str.count('-') * 10)
            score -= len(url_str) * 0.1
            return score

        # Multi-layer Conflict Engine
        def has_conflict(row1, row2):
            text1 = f"{row1['fingerprint']} {row1['Address_internal']}".lower()
            text2 = f"{row2['fingerprint']} {row2['Address_internal']}".lower()
            u1, u2 = str(row1['Address_internal']).lower(), str(row2['Address_internal']).lower()

            # A. Collection/Range Slug Check
            c1 = re.search(r'/collections/([a-z0-9-]+)', u1)
            c2 = re.search(r'/collections/([a-z0-9-]+)', u2)
            if c1 and c2 and c1.group(1) != c2.group(1):
                return True

            # B. Color & Finish Guardrail
            colors = [
                'white', 'black', 'grey', 'gray', 'silver', 'beech', 'oak', 
                'maple', 'walnut', 'ash', 'teak', 'pine', 'blue', 'red', 
                'green', 'yellow', 'purple', 'orange', 'pink', 'wenge'
            ]
            col1 = {c for c in colors if re.search(r'\b' + c + r'\b', text1)}
            col2 = {c for c in colors if re.search(r'\b' + c + r'\b', text2)}
            if col1 != col2:
                return True

            # C. Tray Depth & Spec Check
            depths = ['shallow', 'extra deep', 'deep', 'jumbo']
            d1 = {d for d in depths if d in text1}
            d2 = {d for d in depths if d in text2}
            if d1 and d2 and d1 != d2:
                return True

            # D. Strict Shape Check
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
                if any(term in text for term in ['trapezoidal', 'trapezoid']):
                    tags.add('trap')
                shapes[key] = tags

            if shapes['s1'] and shapes['s2'] and shapes['s1'] != shapes['s2']:
                return True

            # E. Category Check
            categories = ['chair', 'desk', 'table', 'storage', 'screen', 'bench', 'tray', 'cabinet', 'bookcase']
            cat1 = {c for c in categories if c in text1}
            cat2 = {c for c in categories if c in text2}
            if cat1 and cat2 and cat1 != cat2:
                return True

            # F. Material & Finish Check
            materials = {
                'padded': ['seat pad', 'padded', 'upholstered', 'cushion', 'fabric seat'],
                'wooden': ['beech', 'wooden', 'wood', 'plywood', 'timber'],
                'plastic': ['plastic', 'polypropylene', 'poly'],
                'mesh': ['mesh']
            }
            m1 = {tag for tag, terms in materials.items() if any(term in text1 for term in terms)}
            m2 = {tag for tag, terms in materials.items() if any(term in text2 for term in terms)}
            if m1 and m2 and m1 != m2:
                return True

            # G. Feature Flags
            if ('linking' in text1) != ('linking' in text2):
                return True

            return False

        # Internal standardization
        df['Address_internal'] = df[url_col]
        df['cleaned_Title'] = df[title_col].apply(clean_text)
        
        if h1_col != "None" and h1_col in df.columns:
            df['cleaned_H1'] = df[h1_col].apply(clean_text)
            df['fingerprint'] = df['cleaned_Title'] + " " + df['cleaned_H1']
        else:
            df['fingerprint'] = df['cleaned_Title']

        df['extracted_numbers'] = df.apply(get_numbers, axis=1)

        results = []
        processed_urls = set()

        progress_bar = st.progress(0)
        status_text = st.empty()
        total_rows = len(df)

        for index, row in df.iterrows():
            url = row['Address_internal']
            current_fingerprint = row['fingerprint']
            current_numbers = row['extracted_numbers']
            
            progress_bar.progress((index + 1) / total_rows)
            status_text.text(f"Processing row {index + 1} of {total_rows}...")

            if url in processed_urls:
                continue

            if len(current_fingerprint.strip()) < 8 or re.search(r'/[0-9]{1,3}$', str(url)):
                results.append({
                    'URL': url,
                    'Canonical': url,
                    'Is Self-Referencing': 'Yes'
                })
                processed_urls.add(url)
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
        
        st.caption("⚠️ Always double-check the output before sending over to a client.")
        csv_data = mapping_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Canonical Mapping CSV",
            data=csv_data,
            file_name="canonical_mapping.csv",
            mime="text/csv"
        )
