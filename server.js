const express = require('express');
const path = require('path');
const { chromium } = require('playwright');

const app = express();
const port = 4444;

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// async function scrapeWebsite(url) {
//   console.log('Scraping website:', url);
//   const browser = await chromium.launch();
//   const page = await browser.newPage();
  
//   try {
//     // Navigate to the page with a longer timeout
//     await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });

//     // Scroll through the page to trigger lazy-loading
//     await page.evaluate(() => {
//       return new Promise((resolve) => {
//         let totalHeight = 0;
//         const distance = 100;
//         const timer = setInterval(() => {
//           const scrollHeight = document.body.scrollHeight;
//           window.scrollBy(0, distance);
//           totalHeight += distance;

//           if (totalHeight >= scrollHeight) {
//             clearInterval(timer);
//             resolve();
//           }
//         }, 100);
//       });
//     });

//     // Wait an additional second for any final dynamic content to load
//     await page.waitForTimeout(1000);

//     const content = await page.evaluate(() => {
//       const getText = (element) => {
//         const text = element.innerText || element.textContent || '';
//         return text.trim().replace(/\s+/g, ' ');
//       };

//       const getLinks = () => {
//         return Array.from(document.querySelectorAll('a')).map(a => ({
//           text: getText(a),
//           href: a.href
//         }));
//       };

//       // More comprehensive text extraction
//       const extractText = (node) => {
//         if (node.nodeType === Node.TEXT_NODE) {
//           return node.textContent.trim();
//         }
//         if (node.nodeType !== Node.ELEMENT_NODE) {
//           return '';
//         }
//         const style = window.getComputedStyle(node);
//         if (style.display === 'none' || style.visibility === 'hidden') {
//           return '';
//         }
//         return Array.from(node.childNodes)
//           .map(extractText)
//           .join(' ')
//           .replace(/\s+/g, ' ')
//           .trim();
//       };

//       return {
//         title: document.title,
//         text: extractText(document.body),
//         links: getLinks()
//       };
//     });

//     console.log('START');
//     console.log('--------------------------------');
//     console.log('--------------------------------');
//     console.log('--------------------------------');
//     console.log('Scraped content:', content);
//     console.log('--------------------------------');
//     console.log('--------------------------------');
//     console.log('--------------------------------');
//     console.log('END');
//     return content;
//   } finally {
//     await browser.close();
//   }
// }

async function scrapeWebsite(url) {
  console.log('Scraping website:', url);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Navigate to the page with a longer timeout
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });

    // Scroll through the page to trigger lazy-loading
    await page.evaluate(() => {
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
    });

    // Wait an additional second for any final dynamic content to load
    await page.waitForTimeout(1000);

    const content = await page.evaluate(() => {
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

      // More comprehensive text extraction with HTML tag removal
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
        // Skip script and style tags
        if (node.tagName.toLowerCase() === 'script' || node.tagName.toLowerCase() === 'style') {
          return '';
        }
        return Array.from(node.childNodes)
          .map(extractText)
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim();
      };

      // Remove any remaining HTML tags
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
    });

    console.log('Scraped content:', content);
    return content;
  } finally {
    await browser.close();
  }
}

app.post('/scrape', async (req, res) => {
  try {
    const { url } = req.body;
    const result = await scrapeWebsite(url);
    res.json(result);
  } catch (error) {
    console.error('Error in scrape handler:', error);
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
