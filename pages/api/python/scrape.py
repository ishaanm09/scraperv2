from http.server import BaseHTTPRequestHandler
import json
from vc_scraper import extract_companies

def handle_request(event):
    try:
        # Parse the request body
        body = json.loads(event.get('body', '{}'))
        url = body.get('url')
        
        if not url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'URL is required'})
            }
            
        # Extract companies using the scraper
        companies = extract_companies(url)
        
        # Return the results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'companies': [{'name': name, 'url': url} for name, url in companies]
            })
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
        response = handle_request(event)
        
        # Send response
        self.send_response(response['statusCode'])
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(response['body'].encode('utf-8'))

def handler(event, context):
    return handle_request(event) 