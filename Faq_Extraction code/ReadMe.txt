Project Objective
I developed the Universal FAQ Scraper to automate the process of collecting FAQs from different websites and convert them into clean, structured data formats.
The main purpose behind this tool was to simplify dataset creation for chatbots where manual data collection is usually time-consuming and repetitive.

Technology and Tools Used

Language: Python

Framework: Playwright (for browser automation and dynamic content handling)

File Formats: JSONL for structured output and .txt for error logs

Environment: Works in both headless and non-headless browser modes

I chose Playwright because it allows precise control over web interactions, which was necessary for pages that load content dynamically or use JavaScript to reveal answers.

I built the Universal FAQ Scraper to automate the process of collecting FAQs from different websites and convert them into clean, structured data. The goal was to simplify dataset creation for chatbots since manually gathering data is repetitive and time-consuming.

I used Python with Playwright for browser automation because it handles dynamic pages and JavaScript-based content really well. The scraper supports both headless and non-headless modes and saves the results in JSONL format while logging errors in a text file.

The whole system is built around a class called UniversalFAQScraper, which runs based on a configuration dictionary. This setup defines details like the base URL, output paths, browser mode, scraper type, and delay intervals. I wanted to make it modular so that it’s easy to reuse for different websites without rewriting any logic.

When running, the scraper launches a browser, loads the target site, detects whether the layout is hierarchical or expandable, and then runs the appropriate scraping method. It extracts question-answer pairs, cleans the data, and stores it in a structured format. Failed or skipped pages are automatically logged for review.

I also focused on stability — adding proper error handling, timeouts, and retries so the scraper doesn’t stop midway if something fails. It can adapt to different site structures like Freshdesk or Zendesk automatically, making it highly scalable and flexible for large-scale FAQ extraction.

The final output is a clean JSONL dataset that’s ready for fine-tuning or integration with RAG-based chatbots. It also keeps a log file for any failed or missing pages, ensuring no data is lost.

Overall, this project helped me understand web automation, DOM traversal, and data structuring in depth. The Universal FAQ Scraper turned out to be a reliable, adaptable tool that makes large-scale FAQ data collection easier and way more efficient.

Conclusion
Overall, this project strengthened my understanding of web automation, DOM traversal, and structured data extraction.The Universal FAQ Scraper stands as a flexible and reliable solution for large-scale FAQ data collection — combining automation, adaptability, and robustness in a single tool.

