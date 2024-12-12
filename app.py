from flask import Flask, render_template, request, jsonify
import requests
import json
import logging
import sqlite3
import os
from datetime import datetime

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
    
    try:
        response = requests.get("https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json")
        response.raise_for_status()
        
        data = response.json()
        all_articles = data if isinstance(data, list) else data.get('articles', [])
        
        read_articles = get_read_articles()
        categories, unread_counts, total_unread = calculate_counts(all_articles, read_articles)
        
        # Filter articles for display if category is selected
        if selected_category:
            articles = [article for article in all_articles if article.get('category') == selected_category]
        else:
            articles = all_articles
            
        # Add read state to articles
        for article in articles:
            article['is_read'] = article['link'] in read_articles
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        articles = []
        categories = []
        unread_counts = {}
        total_unread = 0
    
    return render_template('index.html', 
                         articles=articles, 
                         categories=categories, 
                         selected_category=selected_category,
                         unread_counts=unread_counts,
                         total_unread=total_unread)

if __name__ == '__main__':
    app.run(debug=True) 