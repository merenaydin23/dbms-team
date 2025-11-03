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


def get_author_profile_url(driver, author_name):
    author_name_formatted = author_name.replace(" ", "+")
    search_url = f'https://scholar.google.com/scholar?hl=tr&q={author_name_formatted}'
    print(f"\n'{author_name}' için yazar profili aranıyor...")
    driver.get(search_url)
    wait = WebDriverWait(driver, 10)
    try:
        profile_link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h4.gs_rt2 a')))
        relative_link = profile_link_element.get_attribute('href')
        print("Yazar profili bulundu.")
        return relative_link
    except Exception:
        print("Arama sonuçlarında bir kullanıcı profili bulunamadı.")
        return None


def get_all_article_links_from_profile(driver, profile_url):
    print(f"Profil sayfasına gidiliyor: {profile_url}")
    driver.get(profile_url)
    wait = WebDriverWait(driver, 10)
    try:
        show_more_button = wait.until(EC.element_to_be_clickable((By.ID, 'gsc_bpf_more')))
        print("'Daha fazla göster' butonuna tıklanarak tüm makaleler yükleniyor...")
        while show_more_button.is_enabled():
            show_more_button.click()
            time.sleep(1.5)
            show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
        print("Tüm makaleler yüklendi.")
    except Exception:
        print("Tüm makaleler zaten görünür durumda veya 'Daha fazla göster' butonu bulunamadı.")
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    article_links = []
    for row in soup.find_all('tr', class_='gsc_a_tr'):
        link_element = row.find('a', class_='gsc_a_at')
        if link_element and link_element.has_attr('href'):
            full_link = "https://scholar.google.com" + link_element['href']
            article_links.append(full_link)
    print(f"Toplam {len(article_links)} makale linki bulundu.")
    return article_links


def scrape_article_details(driver, article_url):
    driver.get(article_url)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.ID, 'gsc_oci_table')))
    except Exception:
        print(f"    -> Detay sayfası yüklenemedi veya içeriği farklı: {article_url}")
        return None

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    details = {}

    title_element = soup.find('a', class_='gsc_oci_title_link')
    details['title'] = title_element.text if title_element else "Başlık Bulunamadı"
    details['source_url'] = title_element['href'] if title_element and title_element.has_attr(
        'href') else "Asıl URL Bulunamadı"

    details['pdf_url'] = "PDF Linki Yok"
    pdf_container = soup.find('div', id='gsc_oci_title_gg')
    if pdf_container:
        pdf_element = pdf_container.find('a')
        if pdf_element and '.pdf' in pdf_element.get('href', ''):
            details['pdf_url'] = pdf_element['href']

    if 'dergipark.org.tr' in details.get('source_url', ''):
        # Dergipark linkini aynı Selenium oturumunda açıyoruz
        print("    -> Dergipark linki tespit edildi. Aynı sekmede PDF aranıyor...")
        details['pdf_url'] = get_dergipark_pdf_link_with_selenium(driver, details['source_url'])

    info_table = soup.find('div', id='gsc_oci_table')
    if info_table:
        for row in info_table.find_all('div', class_='gs_scl'):
            field = row.find('div', class_='gsc_oci_field')
            value = row.find('div', class_='gsc_oci_value')
            if field and value:
                field_key = field.text.strip().lower().replace(' ', '_').replace('-', '_')
                if field_key == "açıklama":
                    details['description'] = value.get_text(strip=True)
                elif field_key == "toplam_alıntı_sayısı":
                    citation_link = value.find('a')
                    details['total_citations'] = citation_link.text.strip() if citation_link else "0"
                else:
                    details[field_key] = value.text.strip()
    return details


def get_dergipark_pdf_link_with_selenium(driver, dergipark_url):
    """(SELENIUM KULLANIR) Dergipark URL'sinden 'Tam Metin' PDF linkini çeker."""
    try:
        driver.get(dergipark_url)
        wait = WebDriverWait(driver, 10)
        # Sayfanın yüklenmesini bekle
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'kt-nav__link-text')))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        pdf_anchor = soup.find('a', class_='kt-nav__link', href=re.compile(r'/download/article-file/'))
        if pdf_anchor and pdf_anchor.has_attr('href'):
            relative_pdf_url = pdf_anchor['href']
            full_pdf_url = f"https://dergipark.org.tr{relative_pdf_url}"
            print("    -> Dergipark PDF linki bulundu.")
            return full_pdf_url
    except Exception as e:
        print(f"    -> Dergipark sayfasında PDF linki bulunurken bir hata oluştu: {e}")
    return "Dergipark PDF Linki Yok"


def save_to_json(data, filename_prefix):
    filename = f"{filename_prefix.replace(' ', '_')}_detailed_articles.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\nVeriler başarıyla '{filename}' dosyasına kaydedildi.")


def main():
    author_name = input("Makalelerini çekmek istediğiniz yazarın adını girin: ")
    if not author_name:
        print("Yazar adı boş bırakılamaz.")
        return

    driver = None
    try:
        options = Options()
        # options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        print("Selenium WebDriver başlatılıyor...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        profile_url = get_author_profile_url(driver, author_name)

        if profile_url:
            article_links = get_all_article_links_from_profile(driver, profile_url)

            all_articles_details = []
            if article_links:
                print("\nHer bir makalenin detay sayfasına gidilerek veriler çekiliyor...")
                for i, link in enumerate(article_links, 1):
                    print(f"[{i}/{len(article_links)}] Makale çekiliyor: {link}")
                    # `requests` yerine `driver` nesnesini kullanarak detayları çekiyoruz
                    details = scrape_article_details(driver, link)
                    if details:
                        all_articles_details.append(details)
                    # Her istek arasında daha uzun ve rastgele bekleme
                    time.sleep(random.uniform(2, 5))

                if all_articles_details:
                    print("\n----- ÇEKİLEN İLK MAKALENİN DETAYLARI -----")
                    pprint.pprint(all_articles_details[0])
                    save_to_json(all_articles_details, author_name)
                else:
                    print("Makale detayları çekilemedi.")
            else:
                print("Profilde hiç makale bulunamadı.")

    except Exception as e:
        print(f"\nProgram çalışırken bir hata oluştu: {e}")

    finally:
        if driver:
            driver.quit()
            print("\nTarayıcı kapatıldı.")


if __name__ == '__main__':
    main()