const puppeteer = require('puppeteer');
(async () => {
    const browser = await puppeteer.launch({ headless: "new", args: ['--no-sandbox'] });
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

    await page.goto('http://127.0.0.1:3000/billing/wallet-managements/manage?action=idvMng', { waitUntil: 'networkidle2' });

    console.log("WAITING for the page to load selects...");
    await page.waitForTimeout(5000);

    // Try finding the v-select components and clicking them
    await page.evaluate(() => {
        console.log("INSIDE BROWSER EVAL...");
        window.tempData = document.querySelector('.custom-select input');
    });

    await browser.close();
})();
