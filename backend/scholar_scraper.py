import time
import random
import json
import re
import requests
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
# ------------------ Yardımcı: URL erişim / HEAD kontrol --------------
# ------------------------------------------------------------------
def url_exists_head(url, timeout=6):
    """HEAD isteği ile URL'nin erişilebilir olup olmadığını kontrol et."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code == 200:
            # Bazı sunucular content-type vermez; 200 yeterli kabul edilebilir
            return True
    except Exception:
        pass
    return False

# ------------------------------------------------------------------
# ------------------ Wiley yardımcı fonksiyonlar --------------------
# ------------------------------------------------------------------
def extract_doi_from_wiley(url):
    """Wiley URL'den DOI kısmını çıkarmaya çalışır."""
    try:
        m = re.search(r'/doi/(?:abs|full|pdf|epdf)/(.+)', url)
        if m:
            return m.group(1)
        m = re.search(r'/doi/(.+)', url)
        if m:
            return m.group(1)
    except:
        pass
    return None

def get_wiley_candidates_from_doi(doi):
    """DOI'den olası Wiley PDF URL'lerini üretir."""
    return [
        f"https://onlinelibrary.wiley.com/doi/pdf/{doi}",
        f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
        f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"
    ]

# ------------------------------------------------------------------
# ------------------ Platform spesifik PDF çekiciler ----------------
# ------------------------------------------------------------------

def get_pdf_from_dergipark(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        pdf_anchor = soup.find('a', class_='kt-nav__link', href=re.compile(r'/download/article-file/'))
        if pdf_anchor and pdf_anchor.get('href'):
            return "https://dergipark.org.tr" + pdf_anchor['href']
    except Exception:
        pass
    return None

def get_pdf_from_mdpi(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # MDPI often uses /article/view/.../pdf or links containing "/pdf"
        a = soup.find("a", href=lambda h: h and "/pdf" in h)
        if a and a.get('href'):
            href = a['href']
            if href.startswith('/'):
                return "https://www.mdpi.com" + href
            return href
    except:
        pass
    # fallback guess
    if "mdpi.com" in url and not url.endswith(".pdf"):
        return url + ".pdf"
    return None

def get_pdf_from_ieee(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # Many IEEE pages don't show PDF href in initial HTML; try to construct from document id
        m = re.search(r'document/(\d+)', url)
        if m:
            arnumber = m.group(1)
            candidate = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}"
            if url_exists_head(candidate):
                return candidate
        # try to find <a> with pdf in page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        a = soup.find("a", href=lambda h: h and "pdf" in h)
        if a and a.get('href'):
            return a['href']
    except:
        pass
    return None

def get_pdf_from_wiley(driver, url):
    try:
        driver.get(url)
        # wait a bit for JS to render
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # 1 - try to find visible 'PDF' link/button via Selenium
        try:
            # bazen link text 'PDF' olabiliyor
            pdf_btn = driver.find_element(By.LINK_TEXT, "PDF")
            href = pdf_btn.get_attribute("href")
            if href:
                return href
        except:
            pass

        # 2 - parse HTML for elements with pdf-download or epdf
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # common class used
        a = soup.find("a", class_=lambda c: c and "pdf" in c.lower())
        if a and a.get('href'):
            href = a['href']
            if href.startswith('/'):
                return "https://onlinelibrary.wiley.com" + href
            return href
        # find any link containing /doi/epdf or /doi/pdf
        for a in soup.find_all("a", href=True):
            if "/doi/epdf" in a['href'] or "/doi/pdf" in a['href'] or "epdf" in a['href']:
                href = a['href']
                if href.startswith('/'):
                    return "https://onlinelibrary.wiley.com" + href
                return href

        # 3 - DOI'den candidate üret ve HEAD ile test et
        doi = extract_doi_from_wiley(url)
        if doi:
            for cand in get_wiley_candidates_from_doi(doi):
                if url_exists_head(cand):
                    return cand
    except:
        pass
    return None

def get_pdf_from_sciencedirect(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # Try to find direct pdf link element by known ids/classes
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # common patterns
        candidates = []
        a = soup.find("a", id=lambda i: i and "pdf" in i.lower())
        if a and a.get('href'):
            candidates.append(a['href'])
        a = soup.find("a", href=lambda h: h and "pdf" in h)
        if a and a.get('href'):
            candidates.append(a['href'])
        # try stamp-like URL (Elsevier sometimes uses /science/article/pii/ -> has PDF path)
        if candidates:
            for href in candidates:
                if href.startswith('/'):
                    full = "https://www.sciencedirect.com" + href
                else:
                    full = href
                if url_exists_head(full):
                    return full
        # fallback: try appending /pdf
        if "/pii/" in url and not url.endswith(".pdf"):
            cand = url + "/pdf"
            if url_exists_head(cand):
                return cand
    except:
        pass
    return None

def get_pdf_from_springer(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        a = soup.find("a", href=lambda h: h and "/content/pdf" in h or (h and h.endswith(".pdf")))
        if a and a.get('href'):
            href = a['href']
            if href.startswith('/'):
                return "https://link.springer.com" + href
            return href
        # fallback guess
        if "/article/" in url:
            cand = url.replace("/article/", "/content/pdf/") + ".pdf"
            if url_exists_head(cand):
                return cand
    except:
        pass
    return None

# For platforms where we decided "login required" or unsupported, return None
def get_pdf_from_researchgate(driver, url): return None
def get_pdf_from_hrcak(driver, url): return None
def get_pdf_from_sagepub(driver, url): return None
def get_pdf_from_euroasiajournal(driver, url): return None
def get_pdf_from_elibrary(driver, url): return None
def get_pdf_from_proquest(driver, url): return None
def get_pdf_from_ssrn(driver, url): return None
def get_pdf_from_academia(driver, url): return None
def get_pdf_from_archive(driver, url): return None

# ------------------------------------------------------------------
# ------------------ Platform dispatcher + guesser ------------------
# ------------------------------------------------------------------
def guess_pdf_url_by_pattern(url):
    """Genel tahmin kuralları (platform bazlı kısa yollar)."""
    u = url.lower()
    # Wiley
    if "onlinelibrary.wiley.com/doi/" in u:
        doi = extract_doi_from_wiley(url)
        if doi:
            for cand in get_wiley_candidates_from_doi(doi):
                if url_exists_head(cand):
                    return cand
            # return first candidate if none responds (still better than None)
            return get_wiley_candidates_from_doi(doi)[0]

    # IEEE
    m = re.search(r'document/(\d+)', u)
    if m:
        ar = m.group(1)
        cand = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={ar}"
        if url_exists_head(cand):
            return cand
        return cand

    # Springer
    if "link.springer.com/article" in u:
        cand = url.replace("/article/", "/content/pdf/") + ".pdf"
        if url_exists_head(cand):
            return cand
        return cand

    # ScienceDirect
    if "sciencedirect.com" in u:
        if "/pii/" in u:
            cand = url + "/pdf"
            if url_exists_head(cand):
                return cand
            return cand

    # MDPI
    if "mdpi.com" in u:
        return url + ".pdf"

    # Generic: try to find any direct .pdf link on page (requests)
    try:
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            a = soup.find("a", href=lambda h: h and h.lower().endswith(".pdf"))
            if a and a.get('href'):
                href = a['href']
                if href.startswith('/'):
                    base = re.match(r'(https?://[^/]+)', url).group(1)
                    return base + href
                return href
    except:
        pass

    return None

def get_pdf_by_platform(driver, url):
    """Önce platform spesifik gerçek PDF arar, yoksa tahmin dener."""
    if not url or url == "Kaynak Yok":
        return None

    # platform-specific attempts
    try:
        if "dergipark.org.tr" in url:
            r = get_pdf_from_dergipark(driver, url)
            if r: return r

        if "mdpi.com" in url:
            r = get_pdf_from_mdpi(driver, url)
            if r: return r

        if "ieeexplore.ieee.org" in url:
            r = get_pdf_from_ieee(driver, url)
            if r: return r

        if "onlinelibrary.wiley.com" in url:
            r = get_pdf_from_wiley(driver, url)
            if r: return r

        if "sciencedirect.com" in url:
            r = get_pdf_from_sciencedirect(driver, url)
            if r: return r

        if "link.springer.com" in url:
            r = get_pdf_from_springer(driver, url)
            if r: return r

        # login-required or unsupported platforms -> return None (we'll fallback to guesser)
        # researchgate, proquest, academia, ssrn, etc return None above

    except Exception:
        pass

    # fallback: pattern-based guess + quick test
    guessed = guess_pdf_url_by_pattern(url)
    return guessed

# ------------------------------------------------------------------
# ------------------ Google Scholar scraping functions --------------
# ------------------------------------------------------------------
def get_author_profile_url(driver, author_name):
    author_name_formatted = author_name.replace(" ", "+")
    search_url = f'https://scholar.google.com/scholar?hl=tr&q={author_name_formatted}'
    driver.get(search_url)
    try:
        profile_link_element = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h4.gs_rt2 a'))
        )
        return profile_link_element.get_attribute('href')
    except Exception:
        return None

def get_all_article_links_from_profile(driver, profile_url):
    driver.get(profile_url)
    try:
        show_more_button = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.ID, 'gsc_bpf_more'))
        )
        while show_more_button.is_enabled():
            try:
                show_more_button.click()
                time.sleep(0.8)
                show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
            except:
                break
    except:
        pass
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    for row in soup.find_all('tr', class_='gsc_a_tr'):
        a = row.find('a', class_='gsc_a_at')
        if a and a.has_attr('href'):
            links.append("https://scholar.google.com" + a['href'])
    return links

def scrape_article_details(driver, article_url):
    driver.get(article_url)
    try:
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.ID, 'gsc_oci_table')))
    except:
        pass
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    details = {}
    title_element = soup.find('a', class_='gsc_oci_title_link')
    details['title'] = title_element.text.strip() if title_element else ""
    details['source_url'] = title_element['href'] if title_element and title_element.has_attr('href') else ""
    # find pdf (platform-specific + guess)
    details['pdf_url'] = get_pdf_by_platform(driver, details['source_url'])
    # other metadata
    info_table = soup.find('div', id='gsc_oci_table')
    if info_table:
        for row in info_table.find_all('div', class_='gs_scl'):
            fld = row.find('div', class_='gsc_oci_field')
            val = row.find('div', class_='gsc_oci_value')
            if fld and val:
                key = fld.text.strip().lower().replace(' ', '_')
                details[key] = val.get_text(strip=True)
    return details

def save_to_json(data, filename_prefix):
    filename = f"{filename_prefix.replace(' ', '_')}_detailed_articles.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Kaydedildi → {filename}")

# ------------------------------------------------------------------
# -------------------------------- MAIN --------------------------------
# ------------------------------------------------------------------
def main():
    author_name = input("Makalelerini çekmek istediğiniz yazarın adını girin: ").strip()
    if not author_name:
        print("Yazar adı boş.")
        return

    options = Options()
    # options.add_argument('--headless')  # isteğe bağlı: görünmeden çalıştırmak için aç
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        profile_url = get_author_profile_url(driver, author_name)
        if not profile_url:
            print("Yazar profili bulunamadı.")
            return

        article_links = get_all_article_links_from_profile(driver, profile_url)
        print(f"{len(article_links)} makale bulundu. Çekiliyor...")

        results = []
        for i, link in enumerate(article_links, 1):
            print(f"[{i}/{len(article_links)}] {link}")
            details = scrape_article_details(driver, link)
            # if pdf_url is None, set to "PDF Yok"
            if not details.get('pdf_url'):
                details['pdf_url'] = "PDF Yok"
            results.append(details)
            time.sleep(random.uniform(1.5, 3.5))

        if results:
            pprint.pprint(results[0])
            save_to_json(results, author_name)

    except Exception as e:
        print("Hata:", e)
    finally:
        driver.quit()

if __name__ == '__main__':
    main()

