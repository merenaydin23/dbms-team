import time
import random
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pprint


# ------------------------------------------------------------------
# ------------------ Yardımcı Fonksiyonlar --------------------------
# ------------------------------------------------------------------

def extract_doi(text_or_url):
    """
    Verilen metin veya URL içinde regex ile DOI (Digital Object Identifier) arar.
    Örnek format: 10.1000/xyz123
    """
    if not text_or_url:
        return None
    # Yaygın DOI regex deseni
    doi_pattern = r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9a-z]+)'
    match = re.search(doi_pattern, text_or_url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def clean_text(text):
    """Metindeki gereksiz boşlukları ve satır sonlarını temizler."""
    if text:
        return text.replace('\xa0', ' ').strip()
    return ""


# ------------------------------------------------------------------
# ------------------ Google Scholar Scraping -----------------------
# ------------------------------------------------------------------

def get_author_profile_url(driver, author_name):
    """Yazar ismini aratıp profil linkini bulur."""
    author_name_formatted = author_name.replace(" ", "+")
    # hl=tr ile Türkçe arayüzü zorluyoruz ki alan adları (Yazarlar, Açıklama vs.) tahmin edilebilir olsun
    search_url = f'https://scholar.google.com/scholar?hl=tr&q={author_name_formatted}'
    driver.get(search_url)
    try:
        # Profil resmi veya ismine tıklanabilir alanı bul
        profile_link_element = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h4.gs_rt2 a'))
        )
        return profile_link_element.get_attribute('href')
    except Exception:
        return None


def get_all_article_links_from_profile(driver, profile_url):
    """Profil sayfasındaki 'Hepsini Göster' butonuna basarak tüm makale linklerini toplar."""
    # Sayfa dilini Türkçe'ye zorlamak için url'e &hl=tr ekleyelim veya emin olalım
    if "hl=tr" not in profile_url:
        profile_url += "&hl=tr"

    driver.get(profile_url)
    try:
        # "Daha fazla göster" (Show more) butonu
        show_more_button = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.ID, 'gsc_bpf_more'))
        )
        # Buton "disabled" olana kadar tıkla
        while show_more_button.is_enabled():
            try:
                show_more_button.click()
                time.sleep(1)  # Yükleme için kısa bekleme
                show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
            except:
                break
    except:
        pass  # Buton yoksa veya hata varsa mevcut listeyle devam et

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    # Tablodaki her satırı gez
    for row in soup.find_all('tr', class_='gsc_a_tr'):
        a = row.find('a', class_='gsc_a_at')
        if a and a.has_attr('href'):
            full_link = "https://scholar.google.com" + a['href']
            links.append(full_link)

    return links


def scrape_article_metadata(driver, article_url):
    """Tek bir makalenin detay sayfasına gidip metadata, abstract ve DOI çeker."""
    driver.get(article_url)

    # Detay tablosunun yüklenmesini bekle
    try:
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.ID, 'gsc_oci_table')))
    except:
        print(f"Hata: Sayfa yüklenemedi -> {article_url}")
        return None

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    details = {
        "title": "",
        "authors": "",
        "publication_date": "",
        "journal": "",
        "abstract": "",
        "doi": "",
        "source_url": "",
        "scholar_url": article_url
    }

    # 1. Başlık ve Kaynak URL
    title_element = soup.find('a', class_='gsc_oci_title_link')
    if title_element:
        details['title'] = clean_text(title_element.text)
        details['source_url'] = title_element['href']
    else:
        # Link yoksa sadece text başlığı al (bazen link olmaz)
        title_div = soup.find('div', id='gsc_oci_title')
        details['title'] = clean_text(title_div.text) if title_div else ""

    # 2. Tablodaki Alanları (Yazarlar, Tarih, Açıklama) Parse Et
    # Google Scholar Türkçe (hl=tr) olduğu için alan adları Türkçe gelecektir.
    info_table = soup.find('div', id='gsc_oci_table')
    if info_table:
        for row in info_table.find_all('div', class_='gs_scl'):
            field_div = row.find('div', class_='gsc_oci_field')
            value_div = row.find('div', class_='gsc_oci_value')

            if field_div and value_div:
                field_name = clean_text(field_div.text).lower().replace(':', '')
                value_text = clean_text(value_div.text)

                if "yazarlar" in field_name or "authors" in field_name:
                    details['authors'] = value_text
                elif "yayın tarihi" in field_name or "publication date" in field_name:
                    details['publication_date'] = value_text
                elif "dergi" in field_name or "journal" in field_name or "kaynak" in field_name or "source" in field_name:
                    details['journal'] = value_text
                elif "açıklama" in field_name or "description" in field_name or "abstract" in field_name:
                    details['abstract'] = value_text

    # 3. DOI Bulma Stratejisi
    # Yöntem A: Eğer kaynak link varsa onun içinde DOI ara
    found_doi = extract_doi(details['source_url'])

    # Yöntem B: Eğer linkte bulamadıysa, Abstract/Açıklama içinde ara
    if not found_doi and details['abstract']:
        found_doi = extract_doi(details['abstract'])

    # Yöntem C: Bazen metadata tablosunda direkt 'Kaynak' satırında link yerine metin olarak geçer
    if not found_doi:
        # Tüm tablo değerlerinde DOI deseni ara
        if info_table:
            found_doi = extract_doi(info_table.get_text())

    details['doi'] = found_doi if found_doi else "DOI Bulunamadı"

    return details


def save_to_json(data, filename_prefix):
    # Dosya ismini güvenli hale getir
    safe_name = "".join([c if c.isalnum() else "_" for c in filename_prefix])
    filename = f"{safe_name}_metadata.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\nVeriler kaydedildi: {filename}")


# ------------------------------------------------------------------
# -------------------------------- MAIN ----------------------------
# ------------------------------------------------------------------
def main():
    target_author = input("Verilerini çekmek istediğiniz Yazar Adını girin: ").strip()
    if not target_author:
        print("Lütfen geçerli bir isim girin.")
        return

    # Tarayıcı Ayarları
    options = Options()
    # options.add_argument('--headless') # Arka planda çalışmasını isterseniz yorum satırını kaldırın
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print(f"'{target_author}' için profil aranıyor...")
        profile_url = get_author_profile_url(driver, target_author)

        if not profile_url:
            print("Yazar profili bulunamadı. İsmi kontrol edin.")
            return

        print(f"Profil bulundu: {profile_url}")
        print("Makale listesi genişletiliyor...")
        article_links = get_all_article_links_from_profile(driver, profile_url)
        print(f"Toplam {len(article_links)} makale linki bulundu. Veri çekme başlıyor...")

        results = []
        for i, link in enumerate(article_links, 1):
            print(f"[{i}/{len(article_links)}] İşleniyor...")

            data = scrape_article_metadata(driver, link)

            if data:
                # Profil sahibinin adını da ekleyelim (User Field)
                data['profile_owner'] = target_author
                results.append(data)

                # Konsola kısa bilgi bas (kontrol için)
                print(f"   -> Başlık: {data['title'][:50]}...")
                print(f"   -> DOI: {data['doi']}")

            # Google Scholar'ın robot kontrolüne takılmamak için rastgele bekleme
            time.sleep(random.uniform(2, 4))

        if results:
            save_to_json(results, target_author)
            print("İşlem tamamlandı.")
        else:
            print("Hiçbir makale verisi çekilemedi.")

    except Exception as e:
        print(f"Beklenmedik bir hata oluştu: {e}")
    finally:
        driver.quit()


if __name__ == '__main__':
    main()