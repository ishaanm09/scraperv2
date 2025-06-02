import { PythonShell } from 'python-shell';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { url } = req.body;

  if (!url) {
    return res.status(400).json({ error: 'URL is required' });
  }

  try {
    const options = {
      mode: 'text',
      pythonPath: 'python3',
      pythonOptions: ['-u'],
      scriptPath: './',
      args: [url]
    };

    const results = await new Promise((resolve, reject) => {
      PythonShell.run('vc_scraper.py', options, (err, results) => {
        if (err) reject(err);
        resolve(results);
      });
    });

    // Parse the results from the Python script
    const companies = [];
    let isDataSection = false;

    for (const line of results) {
      if (line.includes('✅')) {
        break;
      }
      if (line.includes('Company,URL')) {
        isDataSection = true;
        continue;
      }
      if (isDataSection && line.trim()) {
        const [company, url] = line.split(',').map(s => s.trim());
        if (company && url) {
          companies.push([company, url]);
        }
      }
    }

    return res.status(200).json({ companies });
  } catch (error) {
    console.error('Scraping error:', error);
    return res.status(500).json({ error: 'Failed to scrape companies' });
  }
} 