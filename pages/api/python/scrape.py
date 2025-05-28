import json
import sys
import os

# Add the root directory to Python path so we can import vc_scraper
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from vc_scraper import extract_companies

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
            
        # Extract companies using the scraper
        companies = extract_companies(url)
        
        # Return the results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'companies': [{'name': name, 'url': company_url} for name, company_url in companies]
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 