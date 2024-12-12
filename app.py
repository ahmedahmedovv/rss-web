from flask import Flask, render_template, request, jsonify, url_for
import requests
import json
import logging
import sqlite3
import os
from datetime import datetime
from urllib.parse import urlencode, quote_plus

app = Flask(__name__)

# Add logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'articles.db')

# Add these constants at the top of the file after the imports
ARTICLES_PER_PAGE = 10  # Number of articles to show per page

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS read_articles
                    (article_link TEXT PRIMARY KEY)''')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        raise
    finally:
        conn.close()

@app.before_request
def before_request():
    init_db()

def get_read_articles():
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('SELECT article_link FROM read_articles')
    read_articles = {row[0] for row in c.fetchall()}
    conn.close()
    return read_articles

def calculate_counts(articles, read_articles):
    categories = sorted(set(article.get('category', '') for article in articles))
    unread_counts = {}
    total_unread = 0
    
    for category in categories:
        category_articles = [a for a in articles if a.get('category') == category]
        unread_count = sum(1 for a in category_articles if a['link'] not in read_articles)
        unread_counts[category] = unread_count
        total_unread += unread_count
    
    return categories, unread_counts, total_unread

def convert_date_format(date_str):
    """
    Convert various date formats to DD/MM/YYYY
    Input examples: 
    - 'Wed, 11 Dec 2024 13:06:48 -0000'
    - 'Wed, 11 Dec 2024 13:06:48'
    - '2024-12-11'
    - '11-12-2024'
    - '11.12.2024'
    - '2024/12/11'
    - 'December 11, 2024'
    - '11 December 2024'
    - '2024-12-11T18:30:24+00:00'
    - '2024-12-11T20:35:06.362739+00:00'
    Output: '11/12/2024'
    """
    try:
        # Try different date formats
        date_formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # Wed, 11 Dec 2024 13:06:48 -0000
            '%a, %d %b %Y %H:%M:%S',     # Wed, 11 Dec 2024 13:06:48
            '%Y-%m-%d',                   # 2024-12-11
            '%d-%m-%Y',                   # 11-12-2024
            '%d.%m.%Y',                   # 11.12.2024
            '%Y/%m/%d',                   # 2024/12/11
            '%d/%m/%Y',                   # 11/12/2024
            '%B %d, %Y',                  # December 11, 2024
            '%d %B %Y',                   # 11 December 2024
            '%Y%m%d',                     # 20241211
            '%d-%b-%Y',                   # 11-Dec-2024
            '%d %b %Y',                   # 11 Dec 2024
            '%Y-%m-%dT%H:%M:%S%z',        # 2024-12-11T18:30:24+00:00
            '%Y-%m-%dT%H:%M:%S.%f%z',     # 2024-12-11T20:35:06.362739+00:00
            '%Y-%m-%dT%H:%M:%S.%f',       # 2024-12-11T20:35:06.362739
            '%Y-%m-%dT%H:%M:%S',          # 2024-12-11T20:35:06
        ]

        logger.info(f"Converting date: {date_str}")

        # Clean the input string
        if isinstance(date_str, str):
            # Remove extra whitespace and common separators
            date_str = date_str.strip().replace('  ', ' ')
            
            # Remove timezone abbreviations if present
            timezone_abbrs = ['UTC', 'GMT', 'EST', 'PST', 'EDT', 'PDT']
            for abbr in timezone_abbrs:
                date_str = date_str.replace(f' {abbr}', '')

        # Try parsing with standard formats
        for date_format in date_formats:
            try:
                dt = datetime.strptime(date_str, date_format)
                formatted_date = dt.strftime('%d/%m/%Y')
                logger.info(f"Successfully converted {date_str} to {formatted_date}")
                return formatted_date
            except ValueError:
                continue

        # If standard formats fail, try advanced parsing
        if isinstance(date_str, str) and len(date_str) > 0:
            # Handle formats like "Wed, 11 Dec 2024 ..."
            parts = date_str.split()
            if len(parts) >= 3:
                try:
                    # Try to find day, month, and year in the parts
                    day = None
                    month = None
                    year = None
                    
                    for part in parts:
                        # Remove common separators
                        part = part.strip(',:.')
                        
                        # Try to identify year
                        if part.isdigit() and len(part) == 4:
                            year = part
                        # Try to identify day
                        elif part.isdigit() and 1 <= int(part) <= 31:
                            day = part
                        # Try to identify month
                        elif part.lower() in [m.lower() for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']]:
                            month = datetime.strptime(part[:3], '%b').strftime('%m')

                    if all([day, month, year]):
                        return f"{day.zfill(2)}/{month}/{year}"
                except (ValueError, IndexError) as e:
                    logger.error(f"Failed to extract date parts from {date_str}: {e}")

        logger.error(f"Could not parse date: {date_str}")
        return None

    except Exception as e:
        logger.error(f"Error converting date {date_str}: {e}")
        return None

def sort_articles(articles, sort_order='desc'):
    """
    Sort articles by date
    sort_order: 'asc' for ascending, 'desc' for descending
    """
    try:
        # First ensure all articles have a valid published date and convert format
        current_year = datetime.now().year
        
        for article in articles:
            if not article.get('published'):
                logger.warning(f"Missing published date for article: {article.get('optimized_title', 'Unknown title')}")
                article['published'] = f'01/01/{current_year}'
            else:
                # Convert the date format
                converted_date = convert_date_format(article['published'])
                if converted_date:
                    article['published'] = converted_date
                else:
                    logger.warning(f"Could not convert date for article: {article.get('optimized_title', 'Unknown title')}")
                    article['published'] = f'01/01/{current_year}'

        # Sort the articles
        sorted_articles = sorted(
            articles,
            key=lambda x: datetime.strptime(x['published'], '%d/%m/%Y'),
            reverse=(sort_order.lower() == 'desc')
        )
        
        logger.info(f"Sorting {len(articles)} articles, order: {sort_order}")
        logger.info(f"First article date: {sorted_articles[0]['published'] if sorted_articles else 'No articles'}")
        logger.info(f"Last article date: {sorted_articles[-1]['published'] if sorted_articles else 'No articles'}")
        
        return sorted_articles
    except Exception as e:
        logger.error(f"Error sorting articles: {e}")
        return articles  # Return unsorted articles if sorting fails

@app.route('/toggle_read', methods=['POST'])
def toggle_read():
    data = request.json
    article_link = data.get('link')
    
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute('SELECT 1 FROM read_articles WHERE article_link = ?', (article_link,))
    is_read = c.fetchone() is not None
    
    if is_read:
        c.execute('DELETE FROM read_articles WHERE article_link = ?', (article_link,))
    else:
        c.execute('INSERT INTO read_articles (article_link) VALUES (?)', (article_link,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'is_read': not is_read})

@app.route('/get_counts')
def get_counts():
    try:
        response = requests.get("https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json")
        response.raise_for_status()
        
        data = response.json()
        all_articles = data if isinstance(data, list) else data.get('articles', [])
        read_articles = get_read_articles()
        
        _, unread_counts, total_unread = calculate_counts(all_articles, read_articles)
        
        return jsonify({**unread_counts, 'total': total_unread})
    except Exception as e:
        print(f"Error getting counts: {str(e)}")
        return jsonify({'error': 'Failed to get counts'})

@app.route('/')
def index():
    selected_category = request.args.get('category', '')
    sort_order = request.args.get('sort', 'desc')
    page = request.args.get('page', 1, type=int)
    
    logger.info(f"Request params - category: {selected_category}, sort: {sort_order}, page: {page}")
    
    try:
        response = requests.get("https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json")
        response.raise_for_status()
        
        data = response.json()
        all_articles = data if isinstance(data, list) else data.get('articles', [])
        
        # Log the dates before sorting
        if all_articles:
            logger.info(f"Sample dates before sorting: {[a.get('published') for a in all_articles[:3]]}")
        
        read_articles = get_read_articles()
        categories, unread_counts, total_unread = calculate_counts(all_articles, read_articles)
        
        # Filter articles for display if category is selected
        if selected_category:
            articles = [article for article in all_articles if article.get('category') == selected_category]
        else:
            articles = all_articles
            
        # Sort articles
        articles = sort_articles(articles, sort_order)
        
        # Log the dates after sorting
        if articles:
            logger.info(f"Sample dates after sorting: {[a.get('published') for a in articles[:3]]}")
        
        # Calculate pagination
        total_articles = len(articles)
        total_pages = max(1, (total_articles + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE)
        
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        # Slice articles for current page
        start_idx = (page - 1) * ARTICLES_PER_PAGE
        end_idx = start_idx + ARTICLES_PER_PAGE
        paginated_articles = articles[start_idx:end_idx]
            
        # Add read state to articles
        for article in paginated_articles:
            article['is_read'] = article['link'] in read_articles
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        paginated_articles = []
        categories = []
        unread_counts = {}
        total_unread = 0
        total_pages = 1
        page = 1
    
    return render_template('index.html', 
                         articles=paginated_articles, 
                         categories=categories, 
                         selected_category=selected_category,
                         unread_counts=unread_counts,
                         total_unread=total_unread,
                         current_page=page,
                         total_pages=total_pages,
                         sort_order=sort_order,
                         urlencode=urlencode,
                         quote_plus=quote_plus)

@app.template_filter('urlencode')
def urlencode_filter(s):
    if isinstance(s, dict):
        return urlencode(s)
    return s

@app.template_filter('dict_filter')
def dict_filter(d):
    """Remove None values from dict"""
    return {k: v for k, v in d.items() if v}

@app.template_filter('quote_plus')
def quote_plus_filter(s):
    if s is None:
        return ''
    return quote_plus(str(s))

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
    app.run(debug=True) 