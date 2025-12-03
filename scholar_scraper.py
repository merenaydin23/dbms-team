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


# ------------------------------------------------------------------------------------------
# -------------------------- PLATFORM PDF ALMA FONKSİYONLARI -------------------------------
# ------------------------------------------------------------------------------------------

def get_pdf_from_dergipark(driver, url):
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'kt-nav__link-text')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        pdf_anchor = soup.find('a', class_='kt-nav__link', href=re.compile(r'/download/article-file/'))
        if pdf_anchor:
            return "https://dergipark.org.tr" + pdf_anchor['href']
    except:
        pass
    return "Dergipark PDF Yok"


def get_pdf_from_mdpi(driver, url):
    driver.get(url)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    pdf = soup.find("a", href=lambda h: h and "pdf" in h)
    if pdf:
        return "https://www.mdpi.com" + pdf["href"]
    return "MDPI PDF Yok"


def get_pdf_from_ieee(driver, url):
    driver.get(url)
    time.sleep(2)
    try:
        btn = driver.find_element(By.ID, "pdf-link")
        return btn.get_attribute("href")
    except:
        return "IEEE PDF Yok"


def get_pdf_from_wiley(driver, url):
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    pdf = soup.find("a", {"class": "pdf-download"})
    if pdf and pdf.get("href"):
        return "https://onlinelibrary.wiley.com" + pdf["href"]
    return "Wiley PDF Yok"


def get_pdf_from_sciencedirect(driver, url):
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    pdf = soup.find("a", {"id": "pdfDownload"})
    if pdf:
        return "https://www.sciencedirect.com" + pdf["href"]
    return "ScienceDirect PDF Yok"


def get_pdf_from_springer(driver, url):
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    pdf = soup.find("a", href=lambda h: h and "pdf" in h)
    if pdf:
        return "https://link.springer.com" + pdf["href"]
    return "Springer PDF Yok"


def get_pdf_from_researchgate(driver, url):
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    pdf = soup.find("a", href=lambda h: h and ".pdf" in h)
    if pdf:
        return pdf["href"]
    return "ResearchGate PDF Yok (Login gerekebilir)"


# ------------------------------------------------------------------------------------------
# ------------------------- URL'DEN PLATFORM PDF YÖNLENDİRİCİ ------------------------------
# ------------------------------------------------------------------------------------------

def get_pdf_by_platform(driver, url):
    if "dergipark.org.tr" in url:
        return get_pdf_from_dergipark(driver, url)
    if "mdpi.com" in url:
        return get_pdf_from_mdpi(driver, url)
    if "ieeexplore.ieee.org" in url:
        return get_pdf_from_ieee(driver, url)
    if "onlinelibrary.wiley.com" in url:
        return get_pdf_from_wiley(driver, url)
    if "sciencedirect.com" in url:
        return get_pdf_from_sciencedirect(driver, url)
    if "link.springer.com" in url:
        return get_pdf_from_springer(driver, url)
    if "researchgate.net" in url:
        return get_pdf_from_researchgate(driver, url)

    return "Platform desteklenmiyor"


# ------------------------------------------------------------------------------------------
# ------------------------------ GOOGLE SCHOLAR SCRAPER ------------------------------------
# ------------------------------------------------------------------------------------------

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
    except:
        print("Arama sonuçlarında bir kullanıcı profili bulunamadı.")
        return None


def get_all_article_links_from_profile(driver, profile_url):
    print(f"Profil sayfasına gidiliyor: {profile_url}")
    driver.get(profile_url)
    wait = WebDriverWait(driver, 10)
    try:
        show_more_button = wait.until(EC.element_to_be_clickable((By.ID, 'gsc_bpf_more')))
        print("'Daha fazla göster' ile makaleler yükleniyor...")
        while show_more_button.is_enabled():
            show_more_button.click()
            time.sleep(1.5)
            show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
    except:
        print("Tüm makaleler zaten yüklenmiş.")

    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    article_links = []

    for row in soup.find_all('tr', class_='gsc_a_tr'):
        link_element = row.find('a', class_='gsc_a_at')
        if link_element and link_element.has_attr('href'):
            full_link = "https://scholar.google.com" + link_element['href']
            article_links.append(full_link)

    print(f"Toplam {len(article_links)} makale bulundu.")
    return article_links


def scrape_article_details(driver, article_url):
    driver.get(article_url)
    wait = WebDriverWait(driver, 10)

    try:
        wait.until(EC.presence_of_element_located((By.ID, 'gsc_oci_table')))
    except:
        print(f"→ Detay sayfası yüklenemedi: {article_url}")
        return None

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    details = {}

    title_element = soup.find('a', class_='gsc_oci_title_link')
    details['title'] = title_element.text if title_element else "Başlık Yok"
    details['source_url'] = title_element['href'] if title_element else "Kaynak Yok"

    # PDF TARAYICI EKLENDİ
    details['pdf_url'] = get_pdf_by_platform(driver, details['source_url'])

    info_table = soup.find('div', id='gsc_oci_table')
    if info_table:
        for row in info_table.find_all('div', class_='gs_scl'):
            field = row.find('div', class_='gsc_oci_field')
            value = row.find('div', class_='gsc_oci_value')
            if field and value:
                field_key = field.text.strip().lower().replace(' ', '_')
                details[field_key] = value.text.strip()

    return details


def save_to_json(data, filename_prefix):
    filename = f"{filename_prefix.replace(' ', '_')}_detailed_articles.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\nVeriler kaydedildi → {filename}")


# ------------------------------------------------------------------------------------------
# ------------------------------------ MAIN -------------------------------------------------
# ------------------------------------------------------------------------------------------

def main():
    author_name = input("Makalelerini çekmek istediğiniz yazarın adını girin: ")
    if not author_name:
        print("Yazar adı boş bırakılamaz.")
        return

    driver = None
    try:
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')

        print("Selenium başlatılıyor...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        profile_url = get_author_profile_url(driver, author_name)
        if not profile_url:
            return

        article_links = get_all_article_links_from_profile(driver, profile_url)
        all_articles_details = []

        print("\nMakaleler çekiliyor...\n")

        for i, link in enumerate(article_links, 1):
            print(f"[{i}/{len(article_links)}] → {link}")
            details = scrape_article_details(driver, link)
            if details:
                all_articles_details.append(details)
            time.sleep(random.uniform(2, 4))

        if all_articles_details:
            pprint.pprint(all_articles_details[0])
            save_to_json(all_articles_details, author_name)

    except Exception as e:
        print(f"Hata: {e}")

    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    main()
