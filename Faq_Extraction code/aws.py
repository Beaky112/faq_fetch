import requests
from bs4 import BeautifulSoup
import json
import re
import time
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

class AWSFAQExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.faqs = []
        
    def get_urls_from_sitemap(self, sitemap_url):
        """Extract URLs from sitemap"""
        print(f"Fetching sitemap: {sitemap_url}")
        urls = []
        
        try:
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            # Parse XML sitemap
            root = ET.fromstring(response.content)
            
            # Handle sitemap index (contains references to other sitemaps)
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            # Check if it's a sitemap index
            sitemaps = root.findall('.//ns:sitemap/ns:loc', namespace)
            if sitemaps:
                print(f"Found {len(sitemaps)} sub-sitemaps")
                for sitemap in sitemaps[:5]:  # Limit to first 5 sitemaps
                    urls.extend(self.get_urls_from_sitemap(sitemap.text))
            else:
                # It's a regular sitemap with URLs
                url_elements = root.findall('.//ns:url/ns:loc', namespace)
                for url in url_elements:
                    url_text = url.text
                    # Filter for FAQ-related pages
                    if 'faq' in url_text.lower():
                        urls.append(url_text)
                        
                print(f"Found {len(urls)} FAQ URLs in this sitemap")
                
        except Exception as e:
            print(f"Error fetching sitemap: {e}")
            
        return urls
    
    def extract_faqs_from_page(self, url):
        """Extract FAQs from a single page"""
        print(f"\nProcessing: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            page_faqs = {
                'url': url,
                'title': soup.title.string if soup.title else '',
                'questions_answers': []
            }
            
            # Method 1: Look for structured FAQ schema
            schema_faqs = self.extract_schema_faqs(soup)
            if schema_faqs:
                page_faqs['questions_answers'].extend(schema_faqs)
            
            # Method 2: Look for common FAQ patterns
            pattern_faqs = self.extract_pattern_faqs(soup)
            if pattern_faqs:
                page_faqs['questions_answers'].extend(pattern_faqs)
            
            # Method 3: Look for accordion/collapsible sections
            accordion_faqs = self.extract_accordion_faqs(soup)
            if accordion_faqs:
                page_faqs['questions_answers'].extend(accordion_faqs)
            
            # Remove duplicates
            seen = set()
            unique_faqs = []
            for faq in page_faqs['questions_answers']:
                q = faq['question'].strip()
                if q and q not in seen:
                    seen.add(q)
                    unique_faqs.append(faq)
            
            page_faqs['questions_answers'] = unique_faqs
            
            if unique_faqs:
                print(f"  ✓ Found {len(unique_faqs)} Q&A pairs")
                self.faqs.append(page_faqs)
            else:
                print(f"  ✗ No FAQs found")
                
            return page_faqs
            
        except Exception as e:
            print(f"  ✗ Error processing page: {e}")
            return None
    
    def extract_schema_faqs(self, soup):
        """Extract FAQs from JSON-LD schema markup"""
        faqs = []
        
        # Look for FAQ schema
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                if not script.string:
                    continue
                    
                data = json.loads(script.string)
                
                # Handle single object or list
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    continue
                
                for item in data:
                    # Skip if item is not a dict
                    if not isinstance(item, dict):
                        continue
                        
                    if item.get('@type') == 'FAQPage':
                        main_entity = item.get('mainEntity', [])
                        
                        # Ensure main_entity is a list
                        if not isinstance(main_entity, list):
                            main_entity = [main_entity]
                        
                        for entity in main_entity:
                            # Skip if entity is not a dict
                            if not isinstance(entity, dict):
                                continue
                                
                            if entity.get('@type') == 'Question':
                                question = entity.get('name', '')
                                accepted_answer = entity.get('acceptedAnswer', {})
                                
                                # Ensure accepted_answer is a dict
                                if isinstance(accepted_answer, dict):
                                    answer = accepted_answer.get('text', '')
                                else:
                                    answer = ''
                                
                                if question and answer:
                                    faqs.append({
                                        'question': self.clean_text(question),
                                        'answer': self.clean_text(answer)
                                    })
                                    
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                continue
                
        return faqs
    
    def extract_pattern_faqs(self, soup):
        """Extract FAQs based on common HTML patterns"""
        faqs = []
        
        # Pattern 1: dt/dd (definition lists)
        dls = soup.find_all('dl')
        for dl in dls:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            
            for dt, dd in zip(dts, dds):
                question = self.clean_text(dt.get_text())
                answer = self.clean_text(dd.get_text())
                
                if question and answer and len(question) > 10:
                    faqs.append({
                        'question': question,
                        'answer': answer
                    })
        
        # Pattern 2: Headings followed by content
        headings = soup.find_all(['h2', 'h3', 'h4'])
        for heading in headings:
            question = self.clean_text(heading.get_text())
            
            # Check if it looks like a question
            if any(q in question.lower() for q in ['what', 'how', 'why', 'when', 'where', 'which', 'can', 'does', 'is', '?']):
                # Get the next sibling(s) as answer
                answer_parts = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h2', 'h3', 'h4']:
                        break
                    if sibling.name in ['p', 'div', 'ul', 'ol']:
                        answer_parts.append(sibling.get_text())
                
                answer = ' '.join(answer_parts)
                answer = self.clean_text(answer)
                
                if question and answer and len(answer) > 20:
                    faqs.append({
                        'question': question,
                        'answer': answer
                    })
        
        # Pattern 3: div with question/answer classes
        qa_containers = soup.find_all(['div', 'section'], 
                                      class_=re.compile(r'faq|question|qa|accordion', re.I))
        
        for container in qa_containers:
            # Look for question elements
            q_elem = container.find(['h2', 'h3', 'h4', 'strong', 'div'], 
                                   class_=re.compile(r'question|q-|faq-q', re.I))
            a_elem = container.find(['div', 'p'], 
                                   class_=re.compile(r'answer|a-|faq-a', re.I))
            
            if q_elem and a_elem:
                question = self.clean_text(q_elem.get_text())
                answer = self.clean_text(a_elem.get_text())
                
                if question and answer:
                    faqs.append({
                        'question': question,
                        'answer': answer
                    })
        
        return faqs
    
    def extract_accordion_faqs(self, soup):
        """Extract FAQs from accordion/collapsible sections"""
        faqs = []
        
        # Look for AWS-specific accordion patterns
        accordions = soup.find_all(['div', 'section'], 
                                   class_=re.compile(r'accordion|collaps|expand', re.I))
        
        for accordion in accordions:
            # Find buttons/headers (usually questions)
            buttons = accordion.find_all(['button', 'a', 'div'], 
                                        class_=re.compile(r'accordion-.*title|toggle|trigger|header', re.I))
            
            for button in buttons:
                question = self.clean_text(button.get_text())
                
                # Find associated content panel
                content_id = button.get('aria-controls') or button.get('data-target')
                if content_id:
                    content = soup.find(id=content_id.replace('#', ''))
                    if content:
                        answer = self.clean_text(content.get_text())
                        
                        if question and answer and len(answer) > 20:
                            faqs.append({
                                'question': question,
                                'answer': answer
                            })
        
        return faqs
    
    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return ''
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove special characters at start/end
        text = re.sub(r'^[:\-•\s]+|[:\-•\s]+$', '', text)
        
        return text
    
    def save_to_json(self, filename='aws_faqs.json'):
        """Save extracted FAQs to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.faqs, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved {len(self.faqs)} pages with FAQs to {filename}")
    
    def save_to_jsonl(self, filename='aws_faqs.jsonl'):
        """Save extracted FAQs to JSONL file (one Q&A per line)"""
        with open(filename, 'w', encoding='utf-8') as f:
            for page in self.faqs:
                for qa in page['questions_answers']:
                    record = {
                        'url': page['url'],
                        'page_title': page['title'],
                        'question': qa['question'],
                        'answer': qa['answer']
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        total_qas = sum(len(page['questions_answers']) for page in self.faqs)
        print(f"✓ Saved {total_qas} Q&A pairs to {filename}")
    
    def save_to_csv(self, filename='aws_faqs.csv'):
        """Save extracted FAQs to CSV file"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Page Title', 'Question', 'Answer'])
            
            for page in self.faqs:
                for qa in page['questions_answers']:
                    writer.writerow([
                        page['url'],
                        page['title'],
                        qa['question'],
                        qa['answer']
                    ])
        
        total_qas = sum(len(page['questions_answers']) for page in self.faqs)
        print(f"✓ Saved {total_qas} Q&A pairs to {filename}")
    
    def run(self, max_pages=50):
        """Main execution method"""
        print("=" * 80)
        print("AWS FAQ Extractor")
        print("=" * 80)
        
        # Get URLs from sitemap
        sitemap_url = "https://aws.amazon.com/sitemaps/index/"
        urls = self.get_urls_from_sitemap(sitemap_url)
        
        if not urls:
            print("\nNo FAQ URLs found in sitemap. Trying common FAQ pages...")
            # Fallback to common FAQ URLs
            urls = [
                "https://aws.amazon.com/faqs/",
                "https://aws.amazon.com/ec2/faqs/",
                "https://aws.amazon.com/s3/faqs/",
                "https://aws.amazon.com/lambda/faqs/",
                "https://aws.amazon.com/rds/faqs/",
            ]
        
        print(f"\n{'=' * 80}")
        print(f"Found {len(urls)} FAQ pages to process")
        print(f"Processing up to {max_pages} pages...")
        print(f"{'=' * 80}")
        
        # Process each URL
        for i, url in enumerate(urls[:max_pages], 1):
            print(f"\n[{i}/{min(len(urls), max_pages)}]", end=" ")
            self.extract_faqs_from_page(url)
            
            # Be polite - add delay between requests
            time.sleep(1)
        
        # Save results
        print(f"\n{'=' * 80}")
        print("Extraction Complete!")
        print(f"{'=' * 80}")
        
        total_qas = sum(len(page['questions_answers']) for page in self.faqs)
        print(f"Total pages with FAQs: {len(self.faqs)}")
        print(f"Total Q&A pairs extracted: {total_qas}")
        
        if self.faqs:
            self.save_to_json()
            self.save_to_jsonl()
            self.save_to_csv()
        else:
            print("\nNo FAQs were extracted. The pages might use different structures.")

if __name__ == "__main__":
    extractor = AWSFAQExtractor()
    
    # Run the extractor
    # You can adjust max_pages parameter (default: 50)
    extractor.run(max_pages=50)
    
    print("\n" + "=" * 80)
    print("Done! Check the following files for results:")
    print("  - aws_faqs.jsonl (JSONL format - one Q&A per line)")
    print("  - aws_faqs.json (JSON format - structured by page)")
    print("  - aws_faqs.csv (CSV format - flat table)")
    print("=" * 80)