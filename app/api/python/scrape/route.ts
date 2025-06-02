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
    
    // Vercel-specific Python paths
    const pythonPaths = [
      'python3',  // Use system Python first
      'python',   // Fallback to generic Python
      '/var/lang/bin/python3',  // Vercel's Python path
      path.join(rootDir, '.venv/bin/python3'),  // Local venv
    ];

    let pythonPath: string | null = null;
    let lastError: Error | null = null;

    // Try each Python path until one works
    for (const testPath of pythonPaths) {
      try {
        await new Promise((resolve, reject) => {
          const testProcess = spawn(testPath, ['--version']);
          
          let output = '';
          testProcess.stdout.on('data', (data) => {
            output += data.toString();
          });
          
          testProcess.stderr.on('data', (data) => {
            output += data.toString();
          });
          
          testProcess.on('close', (code) => {
            if (code === 0) {
              console.log(`Found Python at ${testPath}: ${output.trim()}`);
              resolve(code);
            } else {
              reject(new Error(`Python test failed with code ${code}: ${output}`));
            }
          });
          
          testProcess.on('error', (err) => {
            reject(err);
          });
        });
        pythonPath = testPath;
        break;
      } catch (error) {
        lastError = error as Error;
        console.log(`Failed to use Python at ${testPath}:`, error);
        continue;
      }
    }

    if (!pythonPath) {
      throw new Error(`No working Python installation found. Last error: ${lastError?.message}`);
    }

    console.log('Using Python path:', pythonPath);
    console.log('Script path:', scriptPath);
    console.log('URL:', url);

    // Run the Python script with enhanced error handling
    let pythonOutput = '';
    let pythonError = '';
    
    await new Promise((resolve, reject) => {
      const pythonProcess = spawn(pythonPath!, [
        scriptPath,
        url
      ], {
        env: {
          ...process.env,
          PYTHONPATH: process.cwd(),
          PYTHONUNBUFFERED: '1',
          PATH: `${process.env.PATH}:/var/lang/bin:/var/task/node_modules/.bin`,
          LAMBDA_TASK_ROOT: process.cwd(),
        }
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
    const csvPath = path.join(process.cwd(), 'portfolio_companies.csv');
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