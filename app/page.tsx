'use client';

import { useState } from 'react';

export default function Home() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [csvBlob, setCsvBlob] = useState<Blob | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setCsvBlob(null);
    
    try {
      const response = await fetch('/api/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to scrape the website');
      }
      
      const blob = await response.blob();
      setCsvBlob(blob);
    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'Failed to scrape the website');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!csvBlob) return;
    
    const downloadUrl = window.URL.createObjectURL(csvBlob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = 'portfolio_companies.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  };

  return (
    <main className="min-h-screen bg-black flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-xl space-y-8">
        <h1 className="text-2xl md:text-3xl font-semibold text-white text-center">
          Rho VC Portfolio Scraper
        </h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Enter URL..."
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-neutral-900 border border-neutral-800 rounded-lg text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          
          {error && (
            <div className="text-red-500 text-sm text-center">
              {error}
            </div>
          )}
          
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {loading ? 'Scraping...' : 'Start Scraping'}
          </button>
        </form>

        {csvBlob && (
          <button
            onClick={handleDownload}
            className="w-full px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors animate-fade-in"
          >
            Download CSV
          </button>
        )}
      </div>
    </main>
  );
} 