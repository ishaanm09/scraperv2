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

    // Decode the URL if it was encoded
    const decodedUrl = decodeURIComponent(url);

    const scriptPath = path.join(process.cwd(), 'vc_scraper.py');
    const wrapperPath = path.join(process.cwd(), 'run-scraper.sh');

    // Run the Python script using the wrapper
    let pythonError = '';
    await new Promise((resolve, reject) => {
      const process = spawn('bash', [
        wrapperPath,
        scriptPath,
        decodedUrl
      ]);

      process.stdout.on('data', (data) => {
        console.log(`Script Output: ${data}`);
      });

      process.stderr.on('data', (data) => {
        pythonError += data.toString();
        console.error(`Script Error: ${data}`);
      });

      process.on('close', (code) => {
        if (code === 0) {
          resolve(code);
        } else {
          reject(new Error(pythonError || `Script exited with code ${code}`));
        }
      });

      process.on('error', (error) => {
        reject(new Error(`Failed to run script: ${error.message}`));
      });
    });

    // Check if the CSV file exists
    const csvPath = path.join(process.cwd(), 'portfolio_companies.csv');
    try {
      const csvContent = await readFile(csvPath, 'utf-8');
      
      // Return the CSV file
      return new NextResponse(csvContent, {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename=portfolio_companies.csv',
        },
      });
    } catch (error) {
      console.error('Error reading CSV file:', error);
      return NextResponse.json(
        { error: 'Failed to read the generated CSV file' },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Error in scraping route:', error);
    // Ensure we always return a properly formatted JSON response
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to scrape the website' },
      { status: 500 }
    );
  }
} 