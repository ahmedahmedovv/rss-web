from flask import Flask, render_template, request
import requests
import json
import logging

app = Flask(__name__)

@app.route('/')
def index():
    selected_category = request.args.get('category', '')
    
    try:
        response = requests.get("https://raw.githubusercontent.com/ahmedahmedovv/rss-ai-category/refs/heads/main/data/categorized_articles.json")
        response.raise_for_status()
        
        # Print raw response for debugging
        print("Raw response:", response.text[:500])  # Print first 500 characters
        
        data = response.json()
        
        # Check if data is a list of articles directly
        if isinstance(data, list):
            articles = data
        else:
            articles = data.get('articles', [])
        
        print(f"Retrieved {len(articles)} articles")
        
        # Verify article structure
        if articles:
            print("Sample article:", articles[0])
        
        # Get unique categories
        categories = sorted(set(article.get('category', '') for article in articles))
        print(f"Available categories: {categories}")
        
        # Filter articles if category is selected
        if selected_category:
            articles = [article for article in articles if article.get('category') == selected_category]
            print(f"Found {len(articles)} articles in category '{selected_category}'")
            
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        articles = []
        categories = []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        articles = []
        categories = []
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        articles = []
        categories = []
    
    return render_template('index.html', articles=articles, categories=categories, selected_category=selected_category)

if __name__ == '__main__':
    app.run(debug=True) 