import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { readFile } from 'fs/promises';
import path from 'path';

// Define the NodeJS.ErrnoException type for spawn errors
interface SpawnError extends Error {
  code?: string;
}

// Configure the route to use Edge Runtime
export const runtime = 'edge';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const { url } = await req.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required' }, { status: 400 });
    }

    // Decode the URL if it was encoded
    const decodedUrl = decodeURIComponent(url);

    // Get absolute paths
    const rootDir = process.cwd();
    const scriptPath = path.join(rootDir, 'vc_scraper.py');
    
    // Try different Python paths
    const pythonPaths = [
      '/var/lang/bin/python3',  // Vercel's Python path
      path.join(rootDir, '.venv', 'bin', 'python3'),  // Local venv
      'python3',  // System Python
      'python'    // Fallback
    ];

    let pythonPath: string | null = null;
    let lastError: Error | null = null;

    // Try each Python path until one works
    for (const testPath of pythonPaths) {
      try {
        await new Promise((resolve, reject) => {
          const testProcess = spawn(testPath, ['--version']);
          testProcess.on('close', (code) => code === 0 ? resolve(code) : reject());
          testProcess.on('error', reject);
        });
        pythonPath = testPath;
        break;
      } catch (error) {
        lastError = error as Error;
        continue;
      }
    }

    if (!pythonPath) {
      throw new Error(`No working Python installation found. Last error: ${lastError?.message}`);
    }

    console.log('Using Python path:', pythonPath);
    console.log('Script path:', scriptPath);
    console.log('URL:', decodedUrl);

    // Run the Python script
    let pythonError = '';
    await new Promise((resolve, reject) => {
      const pythonProcess = spawn(pythonPath!, [
        scriptPath,
        decodedUrl
      ], {
        env: {
          ...process.env,
          PYTHONPATH: process.cwd(),
          PYTHONUNBUFFERED: '1'
        }
      });

      pythonProcess.stdout.on('data', (data) => {
        console.log(`Python Output: ${data}`);
      });

      pythonProcess.stderr.on('data', (data) => {
        pythonError += data.toString();
        console.error(`Python Error: ${data}`);
      });

      pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
        if (code === 0) {
          resolve(code);
        } else {
          reject(new Error(pythonError || `Python process exited with code ${code}`));
        }
      });

      pythonProcess.on('error', (error: SpawnError) => {
        console.error('Python process error:', error);
        reject(new Error(`Failed to start Python process: ${error.message}`));
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