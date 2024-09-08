from flask import Flask, request, jsonify, send_from_directory
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)
port = 4445

def scrape_website(url):
    print(f'Scraping website: {url}')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        try:
            # Navigate to the page with a longer timeout
            page.goto(url, wait_until='networkidle', timeout=60000)

            # Scroll through the page to trigger lazy-loading
            page.evaluate("""
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
            """)

            # Wait an additional second for any final dynamic content to load
            page.wait_for_timeout(1000)

            content = page.evaluate("""
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

            print('Scraped content:', content)
            return content
        finally:
            browser.close()

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
