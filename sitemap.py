import requests
import csv
import xml.etree.ElementTree as ET
import time
from urllib.parse import urlparse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_urls(xml_url):
    """Recursively fetches XML sitemaps and extracts only which.co.uk URLs."""
    extracted_urls = []
    
    try:
        response = requests.get(xml_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        for node in root.iter():
            clean_node_tag = node.tag.split('}')[-1].lower()
            
            # SCENARIO A: The node is a sub-sitemap (Sitemap Index)
            if clean_node_tag == 'sitemap':
                for child in node.iter():
                    if child.tag.split('}')[-1].lower() == 'loc' and child.text:
                        sub_sitemap_url = child.text.strip()
                        print(f"  -> Found nested sitemap, drilling down: {sub_sitemap_url}")
                        time.sleep(0.5) # Be polite to their server
                        
                        # Recursively fetch the contents of this sub-sitemap
                        extracted_urls.extend(fetch_urls(sub_sitemap_url))
                        break # Once we have the loc, break out of this child loop
                        
            # SCENARIO B: The node is a final web page URL
            elif clean_node_tag == 'url':
                loc = ""
                
                for child in node.iter():
                    clean_child_tag = child.tag.split('}')[-1].lower()
                    if clean_child_tag in ('loc', 'href', 'link') and not loc:
                        loc = child.text.strip() if child.text else ""
                
                # Filter to ensure we only get valid which.co.uk pages, not XML files
                if loc and not loc.endswith('.xml'):
                    domain = urlparse(loc).netloc
                    if domain == "which.co.uk" or domain.endswith(".which.co.uk"):
                        extracted_urls.append(loc)
                
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching {xml_url}: {e}")
    except ET.ParseError as e:
        print(f"XML parsing error on {xml_url}: {e}")
        
    return extracted_urls

def main():
    ordered_sitemaps = [
        "https://www.which.co.uk/product-hubs/sitemap/product-hub-pages-sitemap.xml",
        "https://www.which.co.uk/dispatch/glide-reviews-sitemap.xml",
        "https://www.which.co.uk/reviews/sitemaps/product-sitemap-index.xml",
        "https://www.which.co.uk/money/sitemap/money-sitemap.xml",
        "https://www.which.co.uk/news/sitemaps/news.xml",
        "https://www.which.co.uk/news/sitemaps/news-archive.xml",
        "https://www.which.co.uk/feeds/sitemaps/video-sitemap.xml",
        "https://www.which.co.uk/dispatch/policy-and-insight-sitemap.xml"
    ]
    
    csv_filename = "which_active_urls_only.csv"
    
    all_page_urls = [] 
    seen_urls = set()  
    
    print(f"Starting extraction for {len(ordered_sitemaps)} sitemaps...\n")
    
    for i, sitemap in enumerate(ordered_sitemaps):
        print(f"Processing ({i+1}/{len(ordered_sitemaps)}): {sitemap}")
        
        # Dig into sitemaps and indexes for just the URLs
        page_urls = fetch_urls(sitemap)
        
        for url in page_urls:
            if url not in seen_urls:
                seen_urls.add(url)
                all_page_urls.append(url)
                
        time.sleep(0.5)

    print(f"\nWriting {len(all_page_urls)} unique URLs to {csv_filename}...")
    
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["URL"])
        
        for url in all_page_urls:
            writer.writerow([url])
            
    print("\nSuccess! Your CSV is ready with just the URLs.")

if __name__ == "__main__":
    main()