import os
import sys
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# Backend klasörünü Python path'ine ekle
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from scholar_scraper import (
    get_author_profile_url,
    get_all_article_links_from_profile,
    scrape_article_details,
    get_pdf_by_platform
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

app = Flask(__name__)
CORS(app)

# Data klasörü ve JSON dosyası yolu (backend klasöründen bir üst dizine çıkıp data klasörüne git)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTICLES_FILE = os.path.join(DATA_DIR, "articles.json")

def ensure_data_dir():
    """Data klasörünün var olduğundan emin ol"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_articles():
    """articles.json dosyasından makaleleri yükle"""
    ensure_data_dir()
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_articles(articles):
    """Makaleleri articles.json dosyasına kaydet"""
    ensure_data_dir()
    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

def scrape_author_articles(author_name):
    """Yazarın makalelerini çek ve döndür"""
    options = Options()
    # options.add_argument('--headless')  # İsteğe bağlı: görünmeden çalıştırmak için
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        profile_url = get_author_profile_url(driver, author_name)
        if not profile_url:
            return None, "Yazar profili bulunamadı."

        article_links = get_all_article_links_from_profile(driver, profile_url)
        if not article_links:
            return [], "Makale bulunamadı."

        results = []
        for i, link in enumerate(article_links, 1):
            print(f"[{i}/{len(article_links)}] {link}")
            details = scrape_article_details(driver, link)
            # PDF URL yoksa "PDF Yok" olarak ayarla
            if not details.get('pdf_url'):
                details['pdf_url'] = "PDF Yok"
            results.append(details)
            time.sleep(random.uniform(1.5, 3.5))

        return results, None

    except Exception as e:
        return None, str(e)
    finally:
        driver.quit()

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """Tüm makaleleri döndür"""
    try:
        articles = load_articles()
        return jsonify(articles), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scrape', methods=['POST'])
def scrape_articles():
    """Yazar adına göre makaleleri çek ve kaydet"""
    try:
        data = request.get_json()
        author_name = data.get('author_name', '').strip()

        if not author_name:
            return jsonify({"error": "Yazar adı gerekli"}), 400

        # Makaleleri çek
        results, error = scrape_author_articles(author_name)

        if error:
            return jsonify({"error": error}), 400

        if not results:
            return jsonify({
                "message": "Makale bulunamadı",
                "inserted": 0,
                "last": []
            }), 200

        # Mevcut makaleleri yükle
        existing_articles = load_articles()
        
        # Yeni makaleleri ekle (duplicate kontrolü - başlık ve kaynak URL'ye göre)
        existing_titles = {article.get('title', '') for article in existing_articles}
        existing_source_urls = {article.get('source_url', '') for article in existing_articles}
        
        new_articles = []
        for article in results:
            title = article.get('title', '')
            source_url = article.get('source_url', '')
            # Eğer başlık veya kaynak URL zaten varsa ekleme
            if title not in existing_titles and source_url not in existing_source_urls:
                new_articles.append(article)
                existing_titles.add(title)
                existing_source_urls.add(source_url)

        # Yeni makaleleri mevcut listeye ekle
        all_articles = existing_articles + new_articles
        
        # Kaydet
        save_articles(all_articles)

        return jsonify({
            "message": f"{len(new_articles)} yeni makale eklendi",
            "inserted": len(new_articles),
            "last": new_articles
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

