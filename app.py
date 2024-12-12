from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_articles')
def get_articles():
    url = "https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json"
    try:
        response = requests.get(url)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
