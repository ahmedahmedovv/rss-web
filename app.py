from flask import Flask, render_template
import requests
import json

app = Flask(__name__)

@app.route('/')
def index():
    # Fetch JSON data from the URL
    url = "https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json"
    try:
        response = requests.get(url)
        data = response.json()
        # Extract the articles array from the JSON
        articles = data.get('articles', [])
    except:
        articles = {"error": "Failed to fetch data"}
    
    return render_template('index.html', articles=articles)

if __name__ == '__main__':
    app.run(debug=True) 