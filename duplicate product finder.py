import re
from urllib.parse import urlparse, urlunparse

class SEOCanonicalEngine:
    def __init__(self):
        # Target keywords that should be stripped for canonical mapping
        self.modifier_keywords = ["next day delivery", "fully installed"]
        
    def generate_canonical_url(self, url: str, h1: str = "") -> dict:
        """
        Strips modifier keywords from H1/URL and generates the standard canonical URL target.
        """
        parsed = urlparse(url)
        path = parsed.path
        
        # 1. Clean H1 text
        cleaned_h1 = h1
        for kw in self.modifier_keywords:
            cleaned_h1 = re.sub(re.escape(kw), "", cleaned_h1, flags=re.IGNORECASE).strip()
        cleaned_h1 = re.sub(r'\s+', ' ', cleaned_h1)

        # 2. Clean URL slug (slugify target phrases: 'next-day-delivery', 'fully-installed', etc.)
        cleaned_path = path
        for kw in self.modifier_keywords:
            slug_kw = kw.lower().replace(" ", "-")
            # Matches keyword with optional preceding/trailing dashes or slashes
            cleaned_path = re.sub(rf'[-/]?{re.escape(slug_kw)}[-/]?', '/', cleaned_path, flags=re.IGNORECASE)
            # Handle non-dashed versions in slugs (e.g. /fullyinstalled/)
            cleaned_path = re.sub(rf'[-/]?{re.escape(kw.replace(" ", ""))}[-/]?', '/', cleaned_path, flags=re.IGNORECASE)

        # Normalize trailing slashes and multiple consecutive slashes
        cleaned_path = re.sub(r'//+', '/', cleaned_path)
        if not cleaned_path.startswith('/'):
            cleaned_path = '/' + cleaned_path

        # Strip query parameters for pure canonical base
        canonical_url = urlunparse((parsed.scheme, parsed.netloc, cleaned_path, '', '', ''))

        modified = (cleaned_h1 != h1) or (cleaned_path != path) or bool(parsed.query)

        return {
            "canonical_url": canonical_url,
            "cleaned_h1": cleaned_h1,
            "canonical_required": modified
        }

    def score_url(self, url: str) -> dict:
        """
        Calculates the quality score of a given URL based on custom SEO penalty rules.
        """
        parsed = urlparse(url)
        path = parsed.path
        query = parsed.query
        
        score = 0
        applied_penalties = []

        # Rule 1: Heavy Penalty (-1000) for Query Parameters
        if query:
            score -= 1000
            applied_penalties.append("Query Parameters (-1000)")

        # Rule 2: Heavy Penalty (-600) for Pure Numeric SKU URLs (/123033.html)
        filename = path.rstrip('/').split('/')[-1]
        name_without_ext = filename.split('.')[0]
        if name_without_ext.isdigit() and len(name_without_ext) > 0:
            score -= 600
            applied_penalties.append("Pure Numeric SKU (-600)")

        # Rule 3: Penalty (-400) for Paginated Path Slugs (/1/4)
        if re.search(r'/\d+/\d+(/|$)', path):
            score -= 400
            applied_penalties.append("Paginated Path Slug (-400)")

        # Rule 4: Penalty (-300) for Promo Keywords (/sale, /clearance, /express)
        if re.search(r'/(sale|clearance|express)(/|-|_|$)', path, re.IGNORECASE):
            score -= 300
            applied_penalties.append("Promo Keyword (-300)")

        # Rule 5: Hierarchy Penalty (-25 per '/') for Deep Slashes
        # Counts slashes in path (excluding leading/trailing empty splits)
        slash_count = len([segment for segment in path.split('/') if segment])
        slash_penalty = slash_count * 25
        score -= slash_penalty
        applied_penalties.append(f"Deep Slashes Depth ({slash_count} slashes) (-{slash_penalty})")

        # Rule 6: Length Adjustment (1 point deduction per path character)
        length_penalty = len(path)
        score -= length_penalty
        applied_penalties.append(f"Path Length ({length_penalty} chars) (-{length_penalty})")

        return {
            "url": url,
            "score": score,
            "penalties": applied_penalties
        }

    def process_page(self, url: str, h1: str = "") -> dict:
        """
        Full pipeline: evaluates canonical target and scores the given URL.
        """
        canonical_info = self.generate_canonical_url(url, h1)
        url_score = self.score_url(url)
        
        return {
            "input_url": url,
            "input_h1": h1,
            "canonical_target": canonical_info["canonical_url"],
            "cleaned_h1": canonical_info["cleaned_h1"],
            "should_canonicalize": canonical_info["canonical_required"],
            "url_score": url_score["score"],
            "applied_penalties": url_score["penalties"]
        }


# ==========================================
# DEMO & TEST CASES
# ==========================================

if __name__ == "__main__":
    engine = SEOCanonicalEngine()

    test_pages = [
        {
            "url": "https://example.com/boilers/combi-boiler-fully-installed?p=2&sort=asc",
            "h1": "Combi Boiler Fully Installed"
        },
        {
            "url": "https://example.com/clearance/express/next-day-delivery/123033.html",
            "h1": "Worcester 4000 Next Day Delivery"
        },
        {
            "url": "https://example.com/products/heating/boilers/combi/",
            "h1": "Worcester Combi Boiler"
        }
    ]

    for page in test_pages:
        result = engine.process_page(page["url"], page["h1"])
        print(f"URL: {result['input_url']}")
        print(f"H1:  '{result['input_h1']}'")
        print(f" Canonical Target: {result['canonical_target']}")
        print(f" Cleaned H1:       '{result['cleaned_h1']}'")
        print(f" URL Score:        {result['url_score']}")
        print(f" Penalties:        {', '.join(result['applied_penalties'])}")
        print("-" * 70)
