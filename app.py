from flask import Flask, render_template, jsonify, request
import requests
from flask_caching import Cache
from datetime import datetime
import logging
import os
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('rss_app')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=5)
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Cache Configuration
cache_config = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}
app.config.from_mapping(cache_config)
cache = Cache(app)

@app.route('/')
def index():
    logger.info('Accessing home page')
    try:
        # Fetch articles from the API
        url = "https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json"
        response = requests.get(url)
        response.raise_for_status()
        articles = response.json()
        
        # Calculate necessary variables for template
        total_unread = len(articles)
        categories = list(set(article.get('category', '') for article in articles))
        unread_counts = {
            category: len([a for a in articles if a.get('category') == category])
            for category in categories
        }
        selected_category = request.args.get('category')
        
        return render_template('index.html',
                             total_unread=total_unread,
                             categories=categories,
                             unread_counts=unread_counts,
                             selected_category=selected_category)
                             
    except Exception as e:
        logger.error(f"Error preparing index page: {str(e)}")
        # Provide default values when there's an error
        return render_template('index.html',
                             total_unread=0,
                             categories=[],
                             unread_counts={},
                             selected_category=None)

@app.route('/get_articles')
@cache.cached(timeout=300)
def get_articles():
    url = "https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json"
    try:
        logger.info('Fetching articles from external API')
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()
        
        logger.info(f'Successfully fetched {len(data)} articles')
        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data
        })
    except requests.exceptions.RequestException as e:
        logger.error(f'Error fetching articles: {str(e)}')
        return jsonify({"error": "Failed to fetch articles"}), 500
    except ValueError as e:
        logger.error(f'Error parsing JSON response: {str(e)}')
        return jsonify({"error": "Invalid data received from server"}), 500
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/clear_cache')
def clear_cache():
    try:
        cache.delete('get_articles')
        logger.info('Cache cleared successfully')
        return jsonify({"message": "Cache cleared successfully"})
    except Exception as e:
        logger.error(f'Error clearing cache: {str(e)}')
        return jsonify({"error": "Failed to clear cache"}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f'Page not found: {request.url}')
    return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Server Error: {error}')
    return jsonify({"error": "Internal server error"}), 500

@app.route('/mark_category_read', methods=['POST'])
def mark_category_read():
    try:
        data = request.json
        category = data.get('category')
        
        # Get all articles
        response = requests.get("https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json")
        response.raise_for_status()
        data = response.json()
        all_articles = data if isinstance(data, list) else data.get('articles', [])
        
        # Filter articles by category if specified
        if category and category != 'all':
            articles_to_mark = [article['link'] for article in all_articles if article.get('category') == category]
        else:
            articles_to_mark = [article['link'] for article in all_articles]
        
        # Mark articles as read in database
        conn = sqlite3.connect(DATABASE_URL)
        c = conn.cursor()
        c.executemany('INSERT OR IGNORE INTO read_articles (article_link) VALUES (?)', 
                     [(link,) for link in articles_to_mark])
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error marking category as read: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info('Starting Flask application')
    app.run(debug=True)
