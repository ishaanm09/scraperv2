import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { readFile } from 'fs/promises';
import path from 'path';

export async function POST(req: NextRequest) {
  try {
    const { url } = await req.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required' }, { status: 400 });
    }

    // Run the Python script
    await new Promise((resolve, reject) => {
      const pythonProcess = spawn('python', [
        path.join(process.cwd(), '..', 'Scraper', 'vc_scraper.py'),
        url
      ]);

      pythonProcess.stderr.on('data', (data) => {
        console.error(`Python Error: ${data}`);
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          resolve(code);
        } else {
          reject(new Error(`Python process exited with code ${code}`));
        }
      });
    });

    // Read the generated CSV file
    const csvContent = await readFile(
      path.join(process.cwd(), '..', 'Scraper', 'portfolio_companies.csv'),
      'utf-8'
    );

    // Return the CSV file
    return new NextResponse(csvContent, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=portfolio_companies.csv',
      },
    });
  } catch (error) {
    console.error('Error:', error);
    return NextResponse.json(
      { error: 'Failed to scrape the website' },
      { status: 500 }
    );
  }
} 