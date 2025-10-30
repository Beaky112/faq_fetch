from playwright.sync_api import sync_playwright
import json
import time
import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set, Optional, Tuple

class UniversalFAQScraper:
    """
    Universal web scraper for FAQ pages supporting two styles:
    1. Freshdesk-style: Hierarchical solutions with article links
    2. Expandable-style: Single-page FAQs with expand/collapse buttons
    """
    
    def __init__(self, config: Dict):
        """
        Initialize scraper with configuration.
        
        Config structure:
        {
            "base_url": "https://example.com",
            "start_url": "https://example.com/faq",
            "output_file": "output.jsonl",
            "failed_file": "failed.txt",
            "scraper_type": "hierarchical" or "expandable",
            "delay_ms": 900,
            "headless": True,
            "source_name": "Example FAQ"
        }
        """
        self.base_url = config.get("base_url", "")
        self.start_url = config.get("start_url", "")
        self.output_file = config.get("output_file", "scraped_faqs.jsonl")
        self.failed_file = config.get("failed_file", "failed_links.txt")
        self.scraper_type = config.get("scraper_type", "auto")  # auto, hierarchical, expandable
        self.delay_ms = config.get("delay_ms", 900)
        self.headless = config.get("headless", True)
        self.source_name = config.get("source_name", "FAQ")
        
        self.visited_solutions = set()
        self.visited_articles = set()
        
    def normalize_url(self, href: str) -> Optional[str]:
        """Normalize relative/absolute URLs."""
        if not href:
            return None
        href = href.strip()
        if href.startswith("//"):
            parsed = urlparse(self.base_url)
            return parsed.scheme + ":" + href
        if href.startswith("/"):
            return urljoin(self.base_url, href)
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return urljoin(self.base_url + "/", href)
    
    def detect_scraper_type(self, page) -> str:
        """Auto-detect the type of FAQ structure."""
        if self.scraper_type != "auto":
            return self.scraper_type
        
        # Check for hierarchical structure (solution/article links)
        hierarchical_indicators = page.query_selector_all(
            "a[href*='/solutions/'], a[href*='/articles/'], a[href*='/support/']"
        )
        
        # Check for expandable structure (buttons, accordions)
        expandable_indicators = page.query_selector_all(
            "button, [role='button'], summary, details, [class*='accordion'], [class*='expandable']"
        )
        
        if len(hierarchical_indicators) > 10:
            print("🔍 Detected: Hierarchical FAQ structure (like Freshdesk)")
            return "hierarchical"
        elif len(expandable_indicators) > 5:
            print("🔍 Detected: Expandable FAQ structure (like AWS)")
            return "expandable"
        else:
            print("⚠️ Could not detect structure, defaulting to expandable")
            return "expandable"
    
    def scrape(self):
        """Main scraping method that routes to appropriate scraper."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.set_default_navigation_timeout(30000)
            page.set_viewport_size({"width": 1920, "height": 1080})
            
            try:
                print(f"🚀 Navigating to {self.start_url}")
                page.goto(self.start_url, wait_until="networkidle")
                page.wait_for_timeout(self.delay_ms)
                
                # Detect scraper type
                detected_type = self.detect_scraper_type(page)
                
                if detected_type == "hierarchical":
                    self._scrape_hierarchical(page)
                else:
                    self._scrape_expandable(page)
                    
                print("\n✅ Scraping completed!")
                
            finally:
                browser.close()
    
    # ==================== HIERARCHICAL SCRAPER ====================
    
    def _scrape_hierarchical(self, page):
        """Scrape hierarchical FAQ structure (Freshdesk-style)."""
        with open(self.output_file, "w", encoding="utf-8") as out, \
             open(self.failed_file, "w", encoding="utf-8") as failed:
            
            # Collect top-level solution links
            top_solutions = self._collect_solution_links(page)
            print(f"📚 Found {len(top_solutions)} top-level sections")
            
            for category_name, category_url in top_solutions:
                category_url = self.normalize_url(category_url)
                if not category_url or category_url in self.visited_solutions:
                    continue
                
                print(f"\n📂 Processing: {category_name}")
                self.visited_solutions.add(category_url)
                
                try:
                    # Collect all article links
                    article_links = self._collect_article_links(page, category_url)
                    
                    # Check for "See all" or folder links
                    see_all_link = self._get_see_all_link(page)
                    if see_all_link and see_all_link not in self.visited_solutions:
                        folder_articles = self._collect_article_links(page, see_all_link)
                        article_links.update(folder_articles)
                        self.visited_solutions.add(see_all_link)
                    
                    # Handle nested solutions if no articles found
                    if len(article_links) == 0:
                        sub_solutions = self._collect_subsolution_links(page, category_url)
                        for sub_name, sub_url in sub_solutions:
                            if sub_url not in self.visited_solutions:
                                sub_articles = self._collect_article_links(page, sub_url)
                                article_links.update(sub_articles)
                                self.visited_solutions.add(sub_url)
                    
                    print(f"  📄 Found {len(article_links)} articles")
                    
                    # Extract Q&A from each article
                    for article_url in sorted(article_links):
                        if article_url in self.visited_articles:
                            continue
                        self.visited_articles.add(article_url)
                        
                        try:
                            q, a = self._extract_qa_from_article(page, article_url)
                            self._write_hierarchical_output(out, category_name, q, a, article_url)
                            print(f"    ✓ {q[:60]}")
                            page.wait_for_timeout(self.delay_ms)
                        except Exception as e:
                            print(f"    ✗ Failed: {article_url}")
                            failed.write(f"ARTICLE_FAIL\t{article_url}\t{e}\n")
                            failed.flush()
                            
                except Exception as e:
                    print(f"  ✗ Error processing {category_url}: {e}")
                    failed.write(f"CATEGORY_FAIL\t{category_url}\t{e}\n")
                    failed.flush()
    
    def _collect_solution_links(self, page) -> List[Tuple[str, str]]:
        """Collect top-level solution/category links."""
        selectors = [
            "a[href*='/solutions/']",
            "a[href*='/support/']",
            "a[href*='/categories/']",
            "a[href*='/sections/']"
        ]
        
        links = {}
        for selector in selectors:
            elements = page.query_selector_all(selector)
            for el in elements:
                href = self.normalize_url(el.get_attribute("href"))
                if not href or "/articles/" in href:
                    continue
                text = el.inner_text().strip() or href
                links[href] = text
        
        return [(text, href) for href, text in links.items()]
    
    def _collect_article_links(self, page, url: str) -> Set[str]:
        """Collect article links from a solution page with pagination support."""
        found = set()
        visited_pages = set()
        current = url
        
        while current and current not in visited_pages:
            try:
                page.goto(current, wait_until="networkidle")
                page.wait_for_timeout(self.delay_ms)
                visited_pages.add(current)
                
                # Find article links
                selectors = [
                    "a[href*='/articles/']",
                    "a[href*='/article/']",
                    "a.article-link",
                    "a.faq-link"
                ]
                
                for selector in selectors:
                    anchors = page.query_selector_all(selector)
                    for a in anchors:
                        href = self.normalize_url(a.get_attribute("href"))
                        if href:
                            found.add(href)
                
                # Check for pagination
                next_btn = page.query_selector("a[rel='next'], a.next_page, li.next a, a.pagination-next")
                next_href = None
                if next_btn:
                    next_href = self.normalize_url(next_btn.get_attribute("href"))
                
                if not next_href or next_href in visited_pages:
                    break
                current = next_href
                
            except Exception:
                break
        
        return found
    
    def _get_see_all_link(self, page) -> Optional[str]:
        """Get 'See all articles' or folder link."""
        selectors = [
            "a[href*='/folders/']",
            "a.see-all-articles",
            "a.view-all",
            "a:has-text('See all')",
            "a:has-text('View all')"
        ]
        
        for selector in selectors:
            try:
                btn = page.query_selector(selector)
                if btn:
                    return self.normalize_url(btn.get_attribute("href"))
            except:
                continue
        return None
    
    def _collect_subsolution_links(self, page, url: str) -> List[Tuple[str, str]]:
        """Collect sub-solution links."""
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(self.delay_ms)
        
        elements = page.query_selector_all("a[href*='/solutions/'], a[href*='/support/']")
        subs = []
        for el in elements:
            href = self.normalize_url(el.get_attribute("href"))
            if href and "/articles/" not in href and href not in self.visited_solutions:
                text = el.inner_text().strip() or href
                subs.append((text, href))
        return subs
    
    def _extract_qa_from_article(self, page, url: str) -> Tuple[str, str]:
        """Extract question and answer from an article page."""
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(self.delay_ms)
        
        # Extract title/question
        title_selectors = [
            "h1.heading", "h2.heading", "h1.article-title", "h2.article-title",
            ".article-title", ".heading", "h1", "h2", "title"
        ]
        
        question = None
        for sel in title_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if text and len(text) > 5:
                        question = text
                        break
            except:
                continue
        
        if not question:
            question = page.title().strip() or "No title found"
        
        # Extract body/answer
        body_selectors = [
            "article.article-body", "div.article-body", "div#article-body",
            ".article-content", ".solution_body", "article", "main"
        ]
        
        answer = None
        for sel in body_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if text and len(text) > 20:
                        answer = text
                        break
            except:
                continue
        
        if not answer:
            answer = "No answer found"
        
        # Clean whitespace
        question = re.sub(r"\s+", " ", question).strip()
        answer = re.sub(r"\s+", " ", answer).strip()
        
        return question, answer
    
    def _write_hierarchical_output(self, file, category, question, answer, url):
        """Write Q&A in hierarchical format (two-line format)."""
        q_obj = {
            "type": "question",
            "category": category,
            "text": question,
            "url": url,
            "source": self.source_name
        }
        a_obj = {
            "type": "answer",
            "category": category,
            "text": answer,
            "url": url,
            "source": self.source_name
        }
        file.write(json.dumps(q_obj, ensure_ascii=False) + "\n")
        file.write(json.dumps(a_obj, ensure_ascii=False) + "\n")
        file.flush()
    
    # ==================== EXPANDABLE SCRAPER ====================
    
    def _scrape_expandable(self, page):
        """Scrape expandable FAQ structure (AWS-style)."""
        print("🔘 Expanding all FAQ sections...")
        
        # Close popups
        self._close_popups(page)
        
        # Expand all FAQ sections
        expanded = self._expand_all_faqs(page)
        print(f"✅ Expanded {expanded} sections")
        
        time.sleep(2)
        
        # Extract FAQs
        print("📝 Extracting Q&A pairs...")
        faqs = self._extract_expandable_faqs(page)
        
        # Save to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            for faq in faqs:
                f.write(json.dumps(faq, ensure_ascii=False) + "\n")
        
        print(f"💾 Saved {len(faqs)} FAQs to {self.output_file}")
        
        # Show samples
        print("\n📋 Sample FAQs:")
        for i, faq in enumerate(faqs[:3]):
            print(f"\n{i+1}. Q: {faq['question'][:80]}")
            print(f"   A: {faq['answer'][:100]}...")
    
    def _close_popups(self, page):
        """Close any popup dialogs."""
        try:
            close_selectors = [
                "button[aria-label*='close']",
                "button[class*='close']",
                ".modal button",
                "[role='dialog'] button"
            ]
            for selector in close_selectors:
                buttons = page.query_selector_all(selector)
                for btn in buttons[:3]:
                    try:
                        if btn.is_visible():
                            btn.click()
                            time.sleep(0.5)
                    except:
                        pass
        except:
            pass
    
    def _expand_all_faqs(self, page) -> int:
        """Expand all collapsible FAQ sections."""
        expand_selectors = [
            "button", "[role='button']", "summary", "details",
            "[class*='accordion']", "[class*='expandable']", "[class*='toggle']"
        ]
        
        expanded = 0
        for selector in expand_selectors:
            elements = page.query_selector_all(selector)
            for i in range(min(elements.count(), 200)):  # Limit to prevent infinite loops
                try:
                    el = elements.nth(i)
                    if not el.is_visible():
                        continue
                    
                    text = el.inner_text().strip()
                    
                    # Only click elements that look like FAQ expanders
                    if text and ('?' in text or len(text) > 20):
                        el.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        el.click()
                        expanded += 1
                        time.sleep(0.3)
                except:
                    continue
        
        return expanded
    
    def _extract_expandable_faqs(self, page) -> List[Dict]:
        """Extract FAQs from expanded content."""
        faqs = []
        
        # Method 1: Extract from containers
        container_selectors = [
            "[class*='faq']", "[class*='expandable']", "[class*='accordion']",
            "section", "details", "article"
        ]
        
        for selector in container_selectors:
            containers = page.query_selector_all(selector)
            for i in range(containers.count()):
                try:
                    container = containers.nth(i)
                    if container.is_visible():
                        faq = self._extract_faq_from_container(container, len(faqs))
                        if faq:
                            faqs.append(faq)
                            print(f"  ✓ {faq['question'][:60]}")
                except:
                    continue
        
        # Method 2: Text-based extraction if containers fail
        if len(faqs) < 3:
            print("  Using text-based extraction...")
            faqs = self._extract_faqs_from_text(page)
        
        return faqs
    
    def _extract_faq_from_container(self, container, index: int) -> Optional[Dict]:
        """Extract FAQ from a single container element."""
        try:
            text = container.inner_text().strip()
            if not text or len(text) < 20:
                return None
            
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Skip irrelevant content
            skip_keywords = ['sign in', 'create account', 'contact us', 'cookie', 'privacy']
            if any(skip in text.lower() for skip in skip_keywords):
                return None
            
            # Find question and answer
            question = ""
            answer_lines = []
            
            for line in lines:
                if not question and '?' in line and len(line) > 10:
                    question = line
                elif question and line and not line.endswith('?'):
                    answer_lines.append(line)
            
            question = self._clean_text(question)
            answer = self._clean_text(' '.join(answer_lines))
            
            if question and answer and len(answer) > 10:
                return {
                    "id": f"faq_{index+1:03d}",
                    "question": question,
                    "answer": answer,
                    "source": self.source_name,
                    "url": self.start_url
                }
        except:
            pass
        
        return None
    
    def _extract_faqs_from_text(self, page) -> List[Dict]:
        """Extract FAQs by parsing page text."""
        faqs = []
        body_text = page.locator("body").inner_text()
        lines = [line.strip() for line in body_text.split('\n') if line.strip()]
        
        skip_keywords = ['sign in', 'create account', 'contact', 'privacy', 'terms', '©']
        
        current_q = ""
        current_a = []
        
        for line in lines:
            # Skip irrelevant lines
            if any(skip in line.lower() for skip in skip_keywords):
                continue
            
            # Detect questions
            if line.endswith('?') and len(line) > 10:
                # Save previous FAQ
                if current_q and current_a:
                    faq = {
                        "id": f"faq_{len(faqs)+1:03d}",
                        "question": current_q,
                        "answer": ' '.join(current_a),
                        "source": self.source_name,
                        "url": self.start_url
                    }
                    faqs.append(faq)
                    print(f"  ✓ {current_q[:60]}")
                
                current_q = line
                current_a = []
            
            # Collect answer lines
            elif current_q and line and not line.endswith('?') and len(line) > 5:
                current_a.append(line)
        
        # Save last FAQ
        if current_q and current_a:
            faq = {
                "id": f"faq_{len(faqs)+1:03d}",
                "question": current_q,
                "answer": ' '.join(current_a),
                "source": self.source_name,
                "url": self.start_url
            }
            faqs.append(faq)
        
        return faqs
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return ' '.join(text.split())


# ==================== EXAMPLE USAGE ====================

def scrape_freshdesk_style():
    """Example: Scrape Freshdesk-style hierarchical FAQs (like Rentomojo)"""
    config = {
        "base_url": "https://rentomojodesk.freshdesk.com",
        "start_url": "https://rentomojodesk.freshdesk.com/support/home",
        "output_file": "rentomojo_faqs.jsonl",
        "failed_file": "rentomojo_failed.txt",
        "scraper_type": "hierarchical",
        "delay_ms": 900,
        "headless": True,
        "source_name": "Rentomojo FAQ"
    }
    scraper = UniversalFAQScraper(config)
    scraper.scrape()


def scrape_aws_style():
    """Example: Scrape AWS-style expandable FAQs"""
    config = {
        "base_url": "https://aws.amazon.com",
        "start_url": "https://aws.amazon.com/vpc/faqs/",
        "output_file": "aws_vpc_faqs.jsonl",
        "failed_file": "aws_failed.txt",
        "scraper_type": "expandable",
        "delay_ms": 500,
        "headless": False,
        "source_name": "AWS VPC FAQ"
    }
    scraper = UniversalFAQScraper(config)
    scraper.scrape()


def scrape_auto_detect():
    """Example: Auto-detect FAQ structure type"""
    config = {
        "base_url": "https://seller.flipkart.com/faq",
        "start_url": "https://seller.flipkart.com/faq",
        "output_file": "faqs.jsonl",
        "failed_file": "failed.txt",
        "scraper_type": "auto",  # Auto-detect
        "delay_ms": 700,
        "headless": True,
        "source_name": "Example FAQ"
    }
    scraper = UniversalFAQScraper(config)
    scraper.scrape()


if __name__ == "__main__":
    # Choose which example to run:
    
    # Option 1: Scrape Rentomojo (hierarchical)
    scrape_freshdesk_style()
    
    # Option 2: Scrape AWS VPC (expandable)
    # scrape_aws_style()
    
    # Option 3: Auto-detect and scrape any FAQ site
    # scrape_auto_detect()