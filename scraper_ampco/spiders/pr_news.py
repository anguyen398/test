import os
import re
from urllib.parse import urlparse, parse_qs

import scrapy
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('.env')

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

CATEGORY_LABELS = [
    "Retail & E-commerce", "Manufacturing & Industrial", "Pharmaceutical & Healthcare Supply Chain",
    "Food & Agriculture Logistics", "Energy & Commodities Transport", "Technology & AI in Supply Chain",
    "Shipping & Freight", "Warehousing & Distribution", "Transportation & Freight Management",
    "Procurement & Sourcing", "Inventory Management", "Last-Mile Delivery", "Reverse Logistics & Returns Management",
    "AI & Automation in Supply Chain", "Blockchain & Transparency Solutions", "IoT & Smart Logistics",
    "Autonomous Vehicle & Self-driving Trucks", "CHIPS Act & Semiconductor Supply Chain",
    "USMCA, Nearshoring & Friendshoring Trends", "Environmental & Sustainable Regulations",
    "Cybersecurity & Supply Chain Resilience", "Trade Tariffs & Geopolitical Shifts",
    "M&A", "New Partnerships & Collaborations", "Supply Chain Disruptions & Risk Management",
    "Investment & Expansion News", "Bankruptcies & Business Closures", "ESG",
    "North America", "Europe", "Asia-Pacific", "Latin America", "Middle East & Africa"
]

def clean_text(text):
    text = text.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def gpt_classify_and_summarize(title, content):
    prompt = (
        f"Title: {title}\n\n"
        f"Content: {content[:2000]}\n\n"
        f"Please provide:\n"
        f"1. A concise summary (max 128 words).\n"
        f"2. Relevant categories from the following list: {', '.join(CATEGORY_LABELS)}.\n"
        f"Format as:\nSummary: [summary]\nCategories: [category1, category2, ...]"
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )

    reply = response.choices[0].message.content

    summary_match = re.search(r"Summary: (.*?)\nCategories:", reply, re.DOTALL)
    categories_match = re.search(r"Categories: (.*)", reply)

    summary = summary_match.group(1).strip() if summary_match else content[:128]
    categories = categories_match.group(1).strip().strip('[]').split(', ') if categories_match else []

    return summary, categories

class NewsPrSpider(scrapy.Spider):
    name = "pr_news_gpt"
    allowed_domains = ["prnewswire.com"]
    start_urls = [
        "https://www.prnewswire.com/news-releases/consumer-technology-latest-news/supply-chain-logistics-list/?page=1&pagesize=25",
        "https://www.prnewswire.com/news-releases/consumer-technology-latest-news/supply-chain-logistics-list/?page=2&pagesize=25",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_titles = set()
        self.seen_links = set()

    def parse(self, response):
        parsed_url = urlparse(response.url)
        page_number = parse_qs(parsed_url.query).get("page", ["unknown"])[0]

        for article in response.css("div.card"):
            link = article.css("a.newsreleaseconsolidatelink::attr(href)").get()
            full_link = response.urljoin(link) if link else None

            title = article.xpath('.//h3/text()[normalize-space()]').get(default="").strip()
            date = article.xpath('.//h3/small/text()').get(default="").strip()

            if not title or not full_link or title in self.seen_titles or full_link in self.seen_links:
                continue

            self.seen_titles.add(title)
            self.seen_links.add(full_link)

            yield response.follow(full_link, callback=self.parse_article_detail, meta={
                "page": page_number,
                "title": clean_text(title),
                "link": full_link,
                "date": date,
            })

        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_article_detail(self, response):
        title = response.meta["title"]
        date = response.meta["date"]
        page_number = response.meta["page"]
        link = response.meta["link"]

        full_text = response.xpath("string(//div[contains(@class, 'article-body')])").get()
        if not full_text:
            full_text = response.xpath("string(//article)").get()
        if not full_text:
            full_text = response.xpath("string(//div[contains(@class, 'release-body')])").get()
        full_text = clean_text(full_text) if full_text else ""

        summary, categories = gpt_classify_and_summarize(title, full_text)

        yield {
            "page": page_number,
            "title": title,
            "link": link,
            "date": date,
            "categories": categories,
            "summary": summary,
            "full_text": full_text,
        }
