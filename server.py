from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from playwright.async_api import async_playwright
import asyncio
import uvicorn
from fastapi.responses import FileResponse
import os

app = FastAPI()
app.mount("/public", StaticFiles(directory="public"), name="public")

# Serve index.html for the root route
@app.get("/")
async def read_root():
    return FileResponse('public/index.html')

class ScrapeRequest(BaseModel):
    url: str

async def scrape_website(url: str):
    print(f'Scraping website: {url}')
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            # Navigate to the page with a longer timeout
            await page.goto(url, wait_until='networkidle', timeout=60000)

            # Scroll through the page to trigger lazy-loading
            await page.evaluate("""
                () => new Promise((resolve) => {
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
                })
            """)

            # Wait an additional second for any final dynamic content to load
            await page.wait_for_timeout(1000)

            content = await page.evaluate("""
                () => {
                    const getText = (element) => {
                        const text = element.innerText || element.textContent || '';
                        return text.trim().replace(/\s+/g, ' ');
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
                        if (node.tagName.toLowerCase() === 'script' || node.tagName.toLowerCase() === 'style') {
                            return '';
                        }
                        return Array.from(node.childNodes)
                            .map(extractText)
                            .join(' ')
                            .replace(/\s+/g, ' ')
                            .trim();
                    };

                    const removeHtmlTags = (str) => {
                        return str.replace(/<[^>]*>/g, '');
                    };

                    const rawText = extractText(document.body);
                    const cleanText = removeHtmlTags(rawText);

                    return {
                        title: document.title,
                        text: cleanText,
                        links: getLinks()
                    };
                }
            """)

            print('Scraped content:', content)
            return content
        finally:
            await browser.close()

@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    try:
        result = await scrape_website(request.url)
        return result
    except Exception as error:
        print('Error in scrape handler:', str(error))
        raise HTTPException(status_code=500, detail=str(error))

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=4445)
