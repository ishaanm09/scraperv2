from http.server import BaseHTTPRequestHandler
import json
import sys
import os

# Add the root directory to Python path so we can import scraper
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from scraper import scrape_to_csv

def handler(request):
    """
    Vercel serverless function handler
    """
    if request.get('method', '') != 'POST':
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }

    try:
        # Parse the request body
        body = json.loads(request.get('body', '{}'))
        url = body.get('url')
        
        if not url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'URL is required'})
            }
            
        # Get CSV data using the scraper
        csv_data = scrape_to_csv(url)
        
        # Return the CSV data
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=portfolio_companies.csv'
            },
            'body': csv_data
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Get the content length
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Read the request body
        body = self.rfile.read(content_length)
        event = {'body': body.decode('utf-8')}
        
        # Handle the request
        response = handler(event)
        
        # Send response
        self.send_response(response['statusCode'])
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response['body'].encode('utf-8'))