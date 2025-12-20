import time
import random
import glob
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from scholar_scraper_v3 import (
    get_author_profile_url,
    get_all_article_links_from_profile,
    scrape_article_metadata
)


# ------------------------------------------------------------------
# ------------------ Yazar Listesi --------------------------------
# ------------------------------------------------------------------
# Buraya veri çekmek istediğiniz yazar isimlerini ekleyin
AUTHOR_LIST = [
    "İBRAHİM TÜRKOĞLU",
    "ENGİN AVCI",
    "RESUL DAŞ",
    "ERKAN TANYILDIZI",
    "MURAT KARABATAK",
    "FATİH ÖZKAYNAK",
    "ÖZAL YILDIRIM",
    "MUHAMMET BAYKARA",
    "YAMAN AKBULUT",
    "BİHTER DAŞ",
    "FERHAT UÇAR",
    "MURAT AYDOĞAN",
    "VAHTETTİN CEM BAYDOĞAN",
    "ALEV KAYA",
    "OĞUZHAN KATAR",
    "ZÜLFİYE BEYZA METİN",
    "ÖMER MİRAÇ KÖKÇAM",
    "BİLAL ALATAŞ",
    "FATİH ÖZYURT",
    "MUHAMMED TALO",
    "SEDA ARSLAN TUNCER",
    "FATİH DEMİR",
    "ÖZGÜR KARADUMAN",
    "FEYZA ALTUNBEY ÖZBAY",
    "SİNEM AKYOL",
    "ESRA GÜNDOĞAN",
    "İRFAN KILIÇ",
    "KÜBRA ARSLANOĞLU",
    "NİGAR ÖZBEY",
    "ESRA YÜZGEÇ ÖZDEMİR",
]


# ------------------------------------------------------------------
# ------------------ Yardımcı Fonksiyonlar -------------------------
# ------------------------------------------------------------------
PARQUET_DIR = "parquet_data"  # Parquet dosyalarının kaydedileceği klasör


def ensure_parquet_dir():
    """Parquet klasörünün var olduğundan emin olur."""
    if not os.path.exists(PARQUET_DIR):
        os.makedirs(PARQUET_DIR)


def get_parquet_filename(author_name):
    """Yazar adından parquet dosya adını oluşturur (scholar_scraper_v3.py ile aynı mantık)."""
    safe_name = "".join([c if c.isalnum() else "_" for c in author_name])
    return os.path.join(PARQUET_DIR, f"{safe_name}_metadata.parquet")


def parquet_exists(author_name):
    """Yazar için parquet dosyasının mevcut olup olmadığını kontrol eder."""
    filename = get_parquet_filename(author_name)
    return os.path.exists(filename)


def save_to_parquet(data, filename_prefix):
    """Verileri parquet formatında kaydeder (klasör içine)."""
    ensure_parquet_dir()
    safe_name = "".join([c if c.isalnum() else "_" for c in filename_prefix])
    filename = os.path.join(PARQUET_DIR, f"{safe_name}_metadata.parquet")
    
    df = pd.DataFrame(data)
    
    df.to_parquet(
        filename,
        engine="pyarrow",
        compression="snappy",
        index=False
    )
    
    print(f"\nVeriler Parquet formatında kaydedildi: {filename}")


# ------------------------------------------------------------------
# ------------------ Batch Scraping Fonksiyonu ---------------------
# ------------------------------------------------------------------
def scrape_author(driver, author_name):
    """Tek bir yazar için veri çeker ve parquet dosyası oluşturur."""
    print(f"\n{'='*60}")
    print(f"'{author_name}' için işlem başlıyor...")
    print(f"{'='*60}")
    
    try:
        profile_url = get_author_profile_url(driver, author_name)
        
        if not profile_url:
            print(f"⚠️  '{author_name}' için profil bulunamadı. Atlanıyor...")
            return None
        
        print(f"✓ Profil bulundu: {profile_url}")
        print("Makale listesi genişletiliyor...")
        article_links = get_all_article_links_from_profile(driver, profile_url)
        print(f"Toplam {len(article_links)} makale linki bulundu. Veri çekme başlıyor...")
        
        if not article_links:
            print(f"⚠️  '{author_name}' için makale bulunamadı.")
            return None
        
        results = []
        for i, link in enumerate(article_links, 1):
            print(f"[{i}/{len(article_links)}] İşleniyor...")
            
            data = scrape_article_metadata(driver, link)
            
            if data:
                data['profile_owner'] = author_name
                results.append(data)
                
                print(f"   -> Başlık: {data['title'][:50]}...")
                print(f"   -> DOI: {data['doi']}")
            
            # Google Scholar'ın robot kontrolüne takılmamak için rastgele bekleme
            time.sleep(random.uniform(2, 4))
        
        if results:
            save_to_parquet(results, author_name)
            print(f"✓ '{author_name}' için {len(results)} makale verisi kaydedildi.")
            return author_name
        else:
            print(f"⚠️  '{author_name}' için hiçbir makale verisi çekilemedi.")
            return None
            
    except Exception as e:
        print(f"❌ '{author_name}' için hata oluştu: {e}")
        return None


def convert_parquets_to_csv(output_filename="all_authors_combined.csv"):
    """Tüm parquet dosyalarını birleştirip CSV'ye çevirir."""
    print(f"\n{'='*60}")
    print("Parquet dosyaları CSV'ye çevriliyor...")
    print(f"{'='*60}")
    
    # Klasördeki tüm parquet dosyalarını bul
    parquet_pattern = os.path.join(PARQUET_DIR, "*_metadata.parquet")
    parquet_files = glob.glob(parquet_pattern)
    
    if not parquet_files:
        print(f"⚠️  '{PARQUET_DIR}' klasöründe hiç parquet dosyası bulunamadı.")
        return
    
    print(f"Bulunan parquet dosyaları: {len(parquet_files)}")
    
    # Tüm parquet dosyalarını oku ve birleştir
    all_dataframes = []
    for parquet_file in parquet_files:
        try:
            df = pd.read_parquet(parquet_file)
            all_dataframes.append(df)
            file_basename = os.path.basename(parquet_file)
            print(f"✓ {file_basename} okundu ({len(df)} satır)")
        except Exception as e:
            file_basename = os.path.basename(parquet_file)
            print(f"⚠️  {file_basename} okunurken hata: {e}")
    
    if not all_dataframes:
        print("⚠️  Hiçbir parquet dosyası okunamadı.")
        return
    
    # Tüm dataframe'leri birleştir
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    
    # CSV'ye kaydet
    combined_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\n✓ Tüm veriler birleştirildi ve CSV'ye kaydedildi: {output_filename}")
    print(f"  Toplam satır sayısı: {len(combined_df)}")
    print(f"  Toplam sütun sayısı: {len(combined_df.columns)}")
    print(f"  Sütunlar: {', '.join(combined_df.columns.tolist())}")


# ------------------------------------------------------------------
# -------------------------------- MAIN ----------------------------
# ------------------------------------------------------------------
def main():
    if not AUTHOR_LIST:
        print("⚠️  AUTHOR_LIST boş! Lütfen yazar isimlerini ekleyin.")
        print("   Dosyayı açıp AUTHOR_LIST dizisine yazar isimlerini ekleyin.")
        return
    
    # Parquet klasörünün var olduğundan emin ol
    ensure_parquet_dir()
    
    print(f"Toplam {len(AUTHOR_LIST)} yazar için veri çekme işlemi başlıyor...")
    
    # Mevcut parquet dosyalarını kontrol et
    existing_authors = [author for author in AUTHOR_LIST if parquet_exists(author)]
    new_authors = [author for author in AUTHOR_LIST if not parquet_exists(author)]
    
    if existing_authors:
        print(f"\n⏭️  {len(existing_authors)} yazar için parquet dosyası zaten mevcut (atlanacak):")
        for author in existing_authors:
            print(f"   - {author} ({get_parquet_filename(author)})")
    
    if new_authors:
        print(f"\n🔄 {len(new_authors)} yazar için yeni veri çekilecek:")
        for author in new_authors:
            print(f"   - {author}")
    
    # Eğer hiç yeni yazar yoksa, sadece CSV birleştirme yap
    if not new_authors:
        print("\n⚠️  Tüm yazarlar için parquet dosyası zaten mevcut. Sadece CSV birleştirme yapılacak.")
        convert_parquets_to_csv()
        return
    
    # Tarayıcı Ayarları
    options = Options()
    # options.add_argument('--headless')  # Arka planda çalışmasını isterseniz yorum satırını kaldırın
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    successful_authors = []
    failed_authors = []
    skipped_authors = existing_authors.copy()  # Baştan mevcut olanları ekle
    
    try:
        for idx, author_name in enumerate(AUTHOR_LIST, 1):
            print(f"\n[{idx}/{len(AUTHOR_LIST)}] Yazar: {author_name}")
            
            # Eğer parquet dosyası zaten varsa, atla
            if parquet_exists(author_name):
                filename = get_parquet_filename(author_name)
                print(f"⏭️  '{author_name}' için parquet dosyası zaten mevcut: {filename}")
                print(f"   Bu yazar atlanıyor, mevcut dosya kullanılacak.")
                if author_name not in skipped_authors:
                    skipped_authors.append(author_name)
                continue
            
            result = scrape_author(driver, author_name)
            
            if result:
                successful_authors.append(author_name)
            else:
                failed_authors.append(author_name)
            
            # Yazar arası bekleme (robot kontrolü için)
            if idx < len(AUTHOR_LIST):
                wait_time = random.uniform(3, 6)
                print(f"\n⏳ Sonraki yazara geçmeden önce {wait_time:.1f} saniye bekleniyor...")
                time.sleep(wait_time)
        
        # Özet
        print(f"\n{'='*60}")
        print("İŞLEM ÖZETİ")
        print(f"{'='*60}")
        print(f"✓ Yeni çekilen: {len(successful_authors)} yazar")
        if successful_authors:
            print(f"  -> {', '.join(successful_authors)}")
        print(f"⏭️  Atlanan (zaten mevcut): {len(skipped_authors)} yazar")
        if skipped_authors:
            print(f"  -> {', '.join(skipped_authors)}")
        print(f"❌ Başarısız: {len(failed_authors)} yazar")
        if failed_authors:
            print(f"  -> {', '.join(failed_authors)}")
        
        # Parquet dosyalarını CSV'ye çevir (yeni çekilenler + mevcut olanlar)
        total_parquet_count = len(successful_authors) + len(skipped_authors)
        if total_parquet_count > 0:
            convert_parquets_to_csv()
        else:
            print("\n⚠️  Hiçbir yazar için parquet dosyası bulunamadığı için CSV oluşturulamadı.")
            
    except Exception as e:
        print(f"\n❌ Beklenmedik bir hata oluştu: {e}")
    finally:
        driver.quit()
        print("\n✓ Tarayıcı kapatıldı.")


if __name__ == '__main__':
    main()

