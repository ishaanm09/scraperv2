import { NextRequest, NextResponse } from 'next/server';

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

    // Get the host from the request
    const protocol = req.headers.get('x-forwarded-proto') || 'http';
    const host = req.headers.get('host') || 'localhost:3000';
    const baseUrl = `${protocol}://${host}`;

    // Call the Python script using an absolute URL
    const response = await fetch(`${baseUrl}/api/python/scrape`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: decodedUrl }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to scrape: ${error}`);
    }

    // Get the CSV content
    const csvContent = await response.text();

    // Return the CSV file
    return new NextResponse(csvContent, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=portfolio_companies.csv',
      },
    });
  } catch (error) {
    console.error('Error in scraping route:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to scrape the website' },
      { status: 500 }
    );
  }
} 