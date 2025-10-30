Project Objective
I developed the Universal FAQ Scraper to automate the process of collecting FAQs from different websites and convert them into clean, structured data formats.
The main purpose behind this tool was to simplify dataset creation for chatbots where manual data collection is usually time-consuming and repetitive.

Technology and Tools Used

Language: Python

Framework: Playwright (for browser automation and dynamic content handling)

File Formats: JSONL for structured output and .txt for error logs

Environment: Works in both headless and non-headless browser modes

I chose Playwright because it allows precise control over web interactions, which was necessary for pages that load content dynamically or use JavaScript to reveal answers.

Design and Architecture
I structured the scraper as a class-based system called UniversalFAQScraper.
The entire logic is organized around a configuration dictionary that defines:

Base URL of the website

Output file paths

Browser mode

Scraper type (hierarchical, expandable, or auto-detect)

Delay intervals between actions

This modular design makes it easy to reconfigure the scraper for different websites without changing the main codebase.

Implementation Flow
Here’s how I implemented the scraping process step-by-step:

Initialize the scraper with a configuration object.

Launch the browser using Playwright.

Navigate to the target website and wait for it to load completely.

Automatically detect whether the page is hierarchical or expandable.

Based on detection, call the respective scraping function:

_scrape_hierarchical() for multi-level category pages.

_scrape_expandable() for accordion-style pages.

Extract question-and-answer pairs, clean them, and store them in structured format.

Save the data into a JSONL file and record failed URLs in a separate log file.

Error Handling and Stability
During implementation, I added multiple error checks and exception handlers to make the scraper stable.

If a link fails to load, it’s logged and skipped instead of stopping the process.

Timeouts and dynamic delays were implemented to handle slow-loading pages.

Invalid or empty entries are filtered out before saving to the output file.

These additions make the scraper reliable even when dealing with unpredictable or inconsistent websites.

Scalability and Flexibility
I designed the scraper to handle multiple FAQ sources by simply updating the configuration.
It can:

Work across various platforms like Freshdesk, Zendesk, or AWS-style FAQs.

Automatically detect the site’s layout without manual intervention.

Adapt to small structural differences between websites.

This makes it suitable for large-scale data gathering or multi-site automation projects.

Output and Data Handling
The scraper outputs clean, structured data in JSONL format, which is ideal for machine learning or chatbot training.
Each record includes a question, answer, and sometimes the category name.
I also created separate log files for skipped or failed pages to ensure no data is lost during long scraping sessions.

Key Achievements in Implementation

Built a universal system that can automatically identify FAQ structures.

Implemented browser automation and DOM inspection using Playwright.

Designed a modular, configurable architecture for easy reuse.

Ensured fault tolerance through logging, retries, and structured error handling.

Created a dataset-ready output format compatible with fine-tuning and RAG models.

Conclusion
Overall, this project strengthened my understanding of web automation, DOM traversal, and structured data extraction.The Universal FAQ Scraper stands as a flexible and reliable solution for large-scale FAQ data collection — combining automation, adaptability, and robustness in a single tool.
