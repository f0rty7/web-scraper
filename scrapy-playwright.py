from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageMethod
from flask import Flask, request, jsonify, send_from_directory
import os
from multiprocessing import Process, Queue
from twisted.internet import reactor

app = Flask(__name__)
port = 4445

class WebsiteSpider(Spider):
    name = 'website_spider'

    def __init__(self, url=None, *args, **kwargs):
        super(WebsiteSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.result = {}

    def start_requests(self):
        for url in self.start_urls:
            yield Request(
                url,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('evaluate', """
                            () => {
                                return new Promise((resolve) => {
                                    let totalHeight = 0;
                                    const distance = 100;
                                    const timer = setInterval(() => {
                                        const scrollHeight = document.body.scrollHeight;
                                        window.scrollBy(0, distance);
                                        totalHeight += distance;

                                        if (totalHeight >= scrollHeight) {
                                            clearInterval(timer);
                                            resolve();
                                        }
                                    }, 100);
                                });
                            }
                        """),
                        PageMethod('wait_for_timeout', 1000),
                    ],
                ),
                callback=self.parse,
            )

    async def parse(self, response):
        page = response.meta['playwright_page']
        
        content = await page.evaluate("""
            () => {
                const getText = (element) => {
                    const text = element.innerText || element.textContent || '';
                    return text.trim().replace(/\\s+/g, ' ');
                };

                const getLinks = () => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({
                        text: getText(a),
                        href: a.href
                    }));
                };

                const extractText = (node) => {
                    if (node.nodeType === Node.TEXT_NODE) {
                        return node.textContent.trim();
                    }
                    if (node.nodeType !== Node.ELEMENT_NODE) {
                        return '';
                    }
                    const style = window.getComputedStyle(node);
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        return '';
                    }
                    return Array.from(node.childNodes)
                        .map(extractText)
                        .join(' ')
                        .replace(/\\s+/g, ' ')
                        .trim();
                };

                return {
                    title: document.title,
                    text: extractText(document.body),
                    links: getLinks()
                };
            }
        """)

        self.result = content
        print('Scraped content:', content)
        await page.close()

class ScraperRunner:
    def __init__(self, url):
        self.url = url

    def run_spider(self, q):
        try:
            process = CrawlerProcess(settings={
                'TWISTED_REACTOR': 'twisted.internet.asyncio.AsyncioSelectorReactor',
                'DOWNLOAD_HANDLERS': {
                    "http": "scrapy_playwright.handler.PlaywrightDownloadHandler",
                    "https": "scrapy_playwright.handler.PlaywrightDownloadHandler",
                },
                'CONCURRENT_REQUESTS': 1,
                'LOG_LEVEL': 'ERROR'
            })
            runner = process.create_crawler(WebsiteSpider)
            deferred = process.crawl(runner, url=self.url)
            deferred.addBoth(lambda _: reactor.stop())
            reactor.run()
            q.put(runner.spider.result)
        except Exception as e:
            q.put(e)

def scrape_website(url):
    print(f'Scraping website: {url}')
    runner = ScraperRunner(url)
    q = Queue()
    p = Process(target=runner.run_spider, args=(q,))
    p.start()
    result = q.get()
    p.join()

    if isinstance(result, Exception):
        raise result
    return result

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        url = request.json['url']
        result = scrape_website(url)
        return jsonify(result)
    except Exception as error:
        print('Error in scrape handler:', str(error))
        return jsonify({'error': str(error)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path != "" and os.path.exists(os.path.join('public', path)):
        return send_from_directory('public', path)
    else:
        return send_from_directory('public', 'index.html')

if __name__ == '__main__':
    app.run(port=port)