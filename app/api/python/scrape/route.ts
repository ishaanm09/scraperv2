import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { readFile } from 'fs/promises';
import path from 'path';

// Use Node.js runtime for Python execution
export const runtime = 'nodejs';

// Define the SpawnError type for spawn errors
interface SpawnError extends Error {
  code?: string;
}

export async function POST(req: NextRequest) {
  try {
    const { url } = await req.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required' }, { status: 400 });
    }

    // Get absolute paths
    const rootDir = process.cwd();
    const scriptPath = path.join(rootDir, 'vc_scraper.py');
    
    // In Vercel's environment, Python should be available directly
    const pythonPath = 'python3';

    console.log('Using Python path:', pythonPath);
    console.log('Script path:', scriptPath);
    console.log('URL:', url);
    console.log('Current directory:', rootDir);
    console.log('Directory contents:', await readFile(rootDir, { withFileTypes: true }));

    // Run the Python script with enhanced error handling
    let pythonOutput = '';
    let pythonError = '';
    
    await new Promise((resolve, reject) => {
      const pythonProcess = spawn(pythonPath, [
        scriptPath,
        url
      ], {
        env: {
          ...process.env,
          PYTHONPATH: rootDir,
          PYTHONUNBUFFERED: '1',
          PATH: process.env.PATH || '/usr/local/bin:/usr/bin:/bin:/var/lang/bin:/var/task/node_modules/.bin'
        },
        cwd: rootDir
      });

      pythonProcess.stdout.on('data', (data) => {
        const output = data.toString();
        pythonOutput += output;
        console.log(`Python Output: ${output}`);
      });

      pythonProcess.stderr.on('data', (data) => {
        const error = data.toString();
        pythonError += error;
        console.error(`Python Error: ${error}`);
      });

      pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
        if (code === 0) {
          resolve(code);
        } else {
          reject(new Error(pythonError || pythonOutput || `Python process exited with code ${code}`));
        }
      });

      pythonProcess.on('error', (error: SpawnError) => {
        console.error('Python process error:', error);
        reject(new Error(`Failed to start Python process: ${error.message}`));
      });
    });

    // Check if the CSV file exists
    const csvPath = path.join(rootDir, 'portfolio_companies.csv');
    try {
      const csvContent = await readFile(csvPath, 'utf-8');
      
      // Return the CSV content
      return new NextResponse(csvContent, {
        headers: {
          'Content-Type': 'text/csv',
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
    console.error('Error in Python scraping route:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to scrape the website' },
      { status: 500 }
    );
  }
} 