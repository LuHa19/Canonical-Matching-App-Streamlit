import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz

st.title("Luke's Canonical Finder Tool 🔎")
st.write("Upload your HTML crawl export CSV to map duplicate products to their best canonical URL.")

# 1. File Uploader UI Widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# 2. Interactive Control Settings (Noise Words & Strictness Slider)
default_noise = "next-day-delivery, fully-installed, express-delivery, delivery, fast, shipping, free, in-stock, sale"
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
    help="Higher values (like 95%) are much stricter and require almost identical titles to match."
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
            return text.strip()

        # Extract numbers from Title/H1 fingerprint AND URL path
        def get_numbers(row):
            fingerprint = str(row['fingerprint'])
            url_path = str(row['Address'])
            combined = f"{fingerprint} {url_path}"
            return frozenset(re.findall(r'\b\d{1,4}\b', combined))

        # URL SEO Quality Score
        def url_quality_score(url):
            url_str = str(url).lower()
            score = 0
            if 'delivery' in url_str or '/1' in url_str:
                score -= 50
            if re.search(r'/[a-z0-9]{4,8}\.html', url_str):
                score -= 100
            score += (url_str.count('-') * 10)
            score -= len(url_str) * 0.1
            return score

        # Multi-layer Conflict Engine
        def has_conflict(row1, row2):
            text1 = f"{row1['fingerprint']} {row1['Address']}".lower()
            text2 = f"{row2['fingerprint']} {row2['Address']}".lower()
            u1, u2 = str(row1['Address']).lower(), str(row2['Address']).lower()

            # A. Collection/Range Slug Check (e.g., /castle vs /aven)
            c1 = re.search(r'/collections/([a-z0-9-]+)', u1)
            c2 = re.search(r'/collections/([a-z0-9-]+)', u2)
            if c1 and c2 and c1.group(1) != c2.group(1):
                return True

            # B. Numeric SKU Conflict (e.g., 120716c vs 120679c)
            sku1 = re.findall(r'\b\d{5,6}[a-z]?\b', u1)
            sku2 = re.findall(r'\b\d{5,6}[a-z]?\b', u2)
            if sku1 and sku2 and set(sku1) != set(sku2):
                return True

            # C. Color & Finish Guardrail (e.g., White vs Beech vs Unspecified)
            colors = [
                'white', 'black', 'grey', 'gray', 'silver', 'beech', 'oak', 
                'maple', 'walnut', 'ash', 'teak', 'pine', 'blue', 'red', 
                'green', 'yellow', 'purple', 'orange', 'pink', 'wenge'
            ]
            col1 = {c for c in colors if re.search(r'\b' + c + r'\b', text1)}
            col2 = {c for c in colors if re.search(r'\b' + c + r'\b', text2)}
            if col1 != col2:
                return True

            # D. Tray Depth & Spec Check (e.g., Shallow vs Extra Deep)
            depths = ['shallow', 'extra deep', 'deep', 'jumbo']
            d1 = {d for d in depths if d in text1}
            d2 = {d for d in depths if d in text2}
            if d1 and d2 and d1 != d2:
                return True

            # E. Strict Shape Check (Semi-Circular vs Circular vs Rectangular vs Square)
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

            # F. Category Check
            categories = ['chair', 'desk', 'table', 'storage', 'screen', 'bench', 'tray', 'cabinet', 'bookcase']
            cat1 = {c for c in categories if c in text1}
            cat2 = {c for c in categories if c in text2}
            if cat1 and cat2 and cat1 != cat2:
                return True

            # G. Material & Finish Check
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

            # H. Feature Flags (e.g., Linking Chairs)
            if ('linking' in text1) != ('linking' in text2):
                return True

            return False

        df['cleaned_Title 1'] = df['Title 1'].apply(clean_text)
        df['cleaned_H1-1'] = df['H1-1'].apply(clean_text)
        df['fingerprint'] = df['cleaned_Title 1'] + " " + df['cleaned_H1-1']
        df['extracted_numbers'] = df.apply(get_numbers, axis=1)

        results = []
        processed_urls = set()

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

            # Skip matching if title/H1 fingerprint is under 8 characters or generic short URL
            if len(current_fingerprint.strip()) < 8 or re.search(r'/[0-9]{1,3}$', str(url)):
                results.append({
                    'URL': url,
                    'Canonical': url,
                    'Is Self-Referencing': 'Yes'
                })
                processed_urls.add(url)
                continue

            potential_matches = df[df['extracted_numbers'] == current_numbers]
            
            # Fuzzy match on fingerprint using user-selected threshold (default 95%)
            matched_rows = potential_matches[
                potential_matches['fingerprint'].apply(lambda x: fuzz.ratio(current_fingerprint, x) >= similarity_threshold)
            ]
            
            # Run multi-layer conflict engine
            valid_urls = []
            for _, m_row in matched_rows.iterrows():
                if not has_conflict(row, m_row):
                    valid_urls.append(m_row['Address'])

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
