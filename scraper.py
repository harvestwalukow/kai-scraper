'''
Script untuk melakukan scraping data jadwal kereta KAI menggunakan Selenium
untuk berbagai stasiun dan tanggal, lalu menyimpannya ke CSV.
'''
import csv
import time
from datetime import datetime, timedelta
import locale

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, WebDriverException

from bs4 import BeautifulSoup

# Common User-Agent string to mimic a real browser
COMMON_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

def parse_price(price_str):
    # Menghilangkan "Rp ", ",-" dan "." sebagai pemisah ribuan
    return int(price_str.replace("Rp ", "").replace(",-", "").replace(".", ""))

def setup_driver(webdriver_executable_path, headless=False):
    '''Inisialisasi Selenium WebDriver.'''
    try:
        # Coba untuk Chrome terlebih dahulu sebagai contoh umum
        options = webdriver.ChromeOptions()
        options.add_argument(f"user-agent={COMMON_USER_AGENT}")  # Set User-Agent
        options.add_argument("--start-maximized")  # Maksimalkan jendela
        options.add_argument('--disable-blink-features=AutomationControlled') # Mencoba menyembunyikan status automasi
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Jika webdriver_executable_path adalah None atau string kosong, Selenium akan mencoba mencarinya di PATH
        if webdriver_executable_path and webdriver_executable_path.strip():
            driver = webdriver.Chrome(executable_path=webdriver_executable_path, options=options)
        else:
            print("Path WebDriver tidak disediakan, mencoba mencari di PATH sistem...")
            driver = webdriver.Chrome(options=options) # Selenium 4+ bisa tanpa executable_path jika di PATH
        print("ChromeDriver berhasil diinisialisasi.")
        return driver
    except Exception as e:
        print(f"Error saat inisialisasi ChromeDriver: {e}")
        print("Pastikan ChromeDriver sudah terinstal dan path-nya benar atau ada di PATH sistem.")
        print("Anda juga bisa mencoba menggunakan WebDriver lain seperti geckodriver untuk Firefox.")
        return None

def parse_schedule_html_content(html_content, url_queried, query_context):
    '''Mem-parsing konten HTML untuk mengekstrak data jadwal.'''
    train_schedules = []
    soup = BeautifulSoup(html_content, 'html.parser')
    schedule_blocks = soup.find_all('div', class_='data-block list-kereta')

    if not schedule_blocks:
        print("    Tidak ada blok jadwal kereta yang ditemukan di HTML yang diambil.")
        return train_schedules

    for block in schedule_blocks:
        schedule_data = {}
        name_div = block.find('div', class_='name')
        if name_div:
            schedule_data['train_name'] = name_div.find(string=True, recursive=False).strip() if name_div.find(string=True, recursive=False) else ""
            train_number_span = name_div.find('span')
            schedule_data['train_number'] = train_number_span.text.strip("() ") if train_number_span else ""
        else:
            schedule_data['train_name'] = "Tidak tersedia"
            schedule_data['train_number'] = "Tidak tersedia"

        col_one_div = block.find('div', class_='col-one')
        if col_one_div:
            class_divs = col_one_div.find_all('div', recursive=False)
            potential_class_divs = [d for d in class_divs if d != name_div and d.text.strip()]
            if potential_class_divs:
                schedule_data['train_class'] = potential_class_divs[0].text.strip()
            else:
                all_divs_in_col_one = col_one_div.find_all('div')
                if len(all_divs_in_col_one) > 1 and all_divs_in_col_one[-1] != name_div:
                    schedule_data['train_class'] = all_divs_in_col_one[-1].text.strip()
                else:
                    schedule_data['train_class'] = "Tidak tersedia"
        else:
            schedule_data['train_class'] = "Tidak tersedia"

        station_start_div = block.find('div', class_='station station-start')
        schedule_data['departure_station'] = station_start_div.text.strip() if station_start_div else "Tidak tersedia"
        time_start_div = block.find('div', class_='times time-start')
        schedule_data['departure_time'] = time_start_div.text.strip() if time_start_div else "Tidak tersedia"
        date_start_div = block.find('div', class_='station date-start')
        schedule_data['departure_date'] = date_start_div.text.strip() if date_start_div else "Tidak tersedia"

        long_time_div = block.find('div', class_='long-time')
        schedule_data['duration'] = long_time_div.text.strip() if long_time_div else "Tidak tersedia"

        arrival_details = block.find('div', class_='card-arrival')
        if arrival_details:
            station_end_divs = arrival_details.find_all('div', class_='station station-end')
            schedule_data['arrival_station'] = station_end_divs[0].text.strip() if len(station_end_divs) > 0 else "Tidak tersedia"
            schedule_data['arrival_date'] = station_end_divs[1].text.strip() if len(station_end_divs) > 1 else "Tidak tersedia"
            time_end_div = arrival_details.find('div', class_='times time-end')
            schedule_data['arrival_time'] = time_end_div.text.strip() if time_end_div else "Tidak tersedia"
        else:
            schedule_data['arrival_station'] = "Tidak tersedia"
            schedule_data['arrival_date'] = "Tidak tersedia"
            schedule_data['arrival_time'] = "Tidak tersedia"

        price_div = block.find('div', class_='price')
        if price_div and price_div.text.strip() and "Rp" in price_div.text:
            try:
                schedule_data['price'] = parse_price(price_div.text.strip())
            except ValueError:
                schedule_data['price'] = price_div.text.strip()
        else:
            schedule_data['price'] = "Tidak tersedia"

        sisa_kursi_small = block.find('small', class_='sisa-kursi')
        schedule_data['availability'] = sisa_kursi_small.text.strip() if sisa_kursi_small else "Tidak tersedia"
        
        schedule_data['hidden_details'] = {
            'query_url': url_queried, # URL saat ini yang di-scrape oleh Selenium (mungkin berbeda dari yg kita buat)
            **query_context # Gabungkan dengan konteks query awal
        }
        train_schedules.append(schedule_data)
    print(f"    Berhasil mengekstrak {len(train_schedules)} jadwal dari konten HTML ini.")
    return train_schedules

def scrape_kai_with_selenium(driver, origin_name, dest_name, date_str_for_kai_input, adult_passengers, infant_passengers):
    '''Menggunakan Selenium untuk mengisi form, mencari, dan mengambil HTML hasil.'''
    kai_booking_url = "https://booking.kai.id/"
    page_html = None
    actual_url_loaded = None

    try:
        print(f"  Navigasi ke: {kai_booking_url}")
        driver.get(kai_booking_url)
        wait = WebDriverWait(driver, 20) # Tunggu hingga 20 detik

        # Isi Stasiun Asal
        print(f"    Mengisi Stasiun Asal: {origin_name}")
        origin_input = wait.until(EC.presence_of_element_located((By.ID, "origination-flexdatalist")))
        origin_input.clear()
        origin_input.send_keys(origin_name)
        time.sleep(1) # Beri waktu flexdatalist untuk memproses/menampilkan suggestion
        origin_input.send_keys(Keys.ARROW_DOWN) # Coba pilih suggestion pertama
        time.sleep(0.5)
        origin_input.send_keys(Keys.ENTER)
        time.sleep(0.5)

        # Isi Stasiun Tujuan
        print(f"    Mengisi Stasiun Tujuan: {dest_name}")
        destination_input = wait.until(EC.presence_of_element_located((By.ID, "destination-flexdatalist")))
        destination_input.clear()
        destination_input.send_keys(dest_name)
        time.sleep(1)
        destination_input.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.5)
        destination_input.send_keys(Keys.ENTER)
        time.sleep(0.5)

        # Isi Tanggal Keberangkatan
        # Format untuk input tanggal KAI tampaknya DD-Month-YYYY (e.g., 01-May-2025)
        print(f"    Mengisi Tanggal Keberangkatan: {date_str_for_kai_input}")
        date_input = wait.until(EC.presence_of_element_located((By.ID, "departure_dateh")))
        # Mencoba mengatur value via JavaScript karena datepicker bisa kompleks
        driver.execute_script(f"arguments[0].value = '{date_str_for_kai_input}';", date_input)
        # Mungkin perlu trigger change event jika ada listener
        driver.execute_script("$(arguments[0]).trigger('change');", date_input) 
        time.sleep(0.5)

        # Penumpang (Asumsi default 1 dewasa, 0 bayi sudah cukup dan tidak diubah)
        # Jika perlu diubah, cari elemen #dewasa, #infant dan tombol +/- nya.

        # Klik tombol Cari Tiket
        print("    Mengklik tombol Cari & Pesan Tiket...")
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "submit")))
        search_button.click()

        # Tunggu halaman hasil dimuat. Cari salah satu blok data.
        print("    Menunggu hasil pencarian...")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.data-block.list-kereta")))
        print("    Halaman hasil terdeteksi.")
        time.sleep(3) # Beri waktu ekstra untuk semua elemen JS dimuat jika ada
        
        page_html = driver.page_source
        actual_url_loaded = driver.current_url

    except TimeoutException:
        print("    Error: Timeout saat menunggu elemen di halaman KAI.")
    except NoSuchElementException:
        print("    Error: Salah satu elemen form tidak ditemukan di halaman KAI.")
    except ElementNotInteractableException as e:
        print(f"    Error: Elemen tidak dapat diinteraksi: {e}")        
    except Exception as e:
        print(f"    Error tidak terduga saat interaksi Selenium: {e}")
    
    return page_html, actual_url_loaded

def save_to_csv(data_list, csv_file_path):
    if not data_list:
        print("Tidak ada data untuk disimpan ke CSV.")
        return
    all_hidden_keys = set()
    for item in data_list:
        if 'hidden_details' in item and isinstance(item['hidden_details'], dict):
            for key in item['hidden_details'].keys():
                all_hidden_keys.add(f"hidden_{key}")
    if not data_list: return
    base_fieldnames = [key for key in data_list[0].keys() if key != 'hidden_details']
    fieldnames = base_fieldnames + sorted(list(all_hidden_keys))
    try:
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for item in data_list:
                item_to_write = item.copy()
                if 'hidden_details' in item_to_write and isinstance(item_to_write['hidden_details'], dict):
                    for h_key, h_value in item_to_write['hidden_details'].items():
                        item_to_write[f"hidden_{h_key}"] = h_value
                    del item_to_write['hidden_details']
                writer.writerow(item_to_write)
        print(f"Data berhasil disimpan ke '{csv_file_path}'")
    except IOError:
        print(f"Error: Tidak dapat menulis ke file CSV '{csv_file_path}'.")
    except Exception as e:
        print(f"Error saat menyimpan ke CSV: {e}")

if __name__ == '__main__':
    # --- KONFIGURASI PENGAMBILAN DATA ---
    # Ganti dengan path absolut ke chromedriver.exe Anda jika tidak ada di PATH sistem
    # atau jika Anda tidak meletakkannya di folder yang sama dengan skrip.
    # Contoh untuk Windows: "C:/path/to/chromedriver.exe"
    # Contoh untuk Linux/MacOS: "/usr/local/bin/chromedriver"
    # Jika string kosong atau None, Selenium akan mencoba mencarinya di PATH.
    WEBDRIVER_PATH = ""

    RUN_HEADLESS = False # Set ke True untuk menjalankan Chrome tanpa UI (di background)

    origin_stations = [
        ("SURABAYA PASAR TURI", "SBI"),
        ("SURABAYA", "SBI")
    ]
    destination_stations = [
        ("PASARSENEN", "PSE"),
        ("GAMBIR", "GMR"),
        ("JAKARTA KOTA", "JAKK"),
        ("JATINEGARA", "JNG")    
    ]
    start_date_str = "2025-06-02"
    num_days_to_scrape = 30 # Kurangi dulu untuk testing awal
    adult_passengers = 1
    infant_passengers = 0
    delay_between_searches = 5 # Jeda lebih lama antar pencarian KAI
    csv_output_filename = "jadwal_kereta_selenium.csv"
    # --- AKHIR KONFIGURASI ---

    all_extracted_data = []
    locale_set_successfully = False
    # Mencoba mengatur locale ke Bahasa Indonesia untuk format nama bulan
    indonesian_locales = ['id_ID.UTF-8', 'id_ID', 'Indonesian_Indonesia.1252'] # Tambahkan variasi umum
    for loc in indonesian_locales:
        try:
            locale.setlocale(locale.LC_TIME, loc)
            locale_set_successfully = True
            print(f"Locale '{loc}' berhasil diatur untuk format tanggal (nama bulan akan dalam Bahasa Indonesia).")
            break # Hentikan jika berhasil
        except locale.Error:
            print(f"Gagal mengatur locale '{loc}'. Mencoba alternatif...")
    
    if not locale_set_successfully:
        print("PERINGATAN: Tidak ada locale Bahasa Indonesia yang berhasil diatur. Akan digunakan pemetaan bulan manual.")

    try:
        start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: Format tanggal mulai '{start_date_str}' salah. Gunakan format YYYY-MM-DD.")
        exit()

    driver = setup_driver(WEBDRIVER_PATH, headless=RUN_HEADLESS)
    if not driver:
        print("Gagal setup WebDriver. Program berhenti.")
        exit()

    print("Memulai proses scraping otomatis dengan Selenium...")
    try:
        for origin_name, origin_code in origin_stations:
            for dest_name, dest_code in destination_stations:
                print(f"\nMencari rute: {origin_name} ({origin_code}) -> {dest_name} ({dest_code})")
                for i in range(num_days_to_scrape):
                    current_date_obj = start_date_obj + timedelta(days=i)
                    # Format tanggal untuk input ke form KAI (DD-NamaBulan-YYYY, misal 02-Juni-2025)
                    date_str_for_kai_form = ""

                    if locale_set_successfully:
                        try:
                            date_str_for_kai_form = current_date_obj.strftime("%d-%B-%Y")
                            print(f"  Format tanggal (dari locale '{locale.getlocale(locale.LC_TIME)[0]}'): {date_str_for_kai_form}")
                        except Exception as e:
                            print(f"  Error saat format tanggal dengan locale: {e}. Menggunakan fallback manual.")
                            locale_set_successfully = False # Anggap locale gagal jika strftime error
                    
                    if not locale_set_successfully or not date_str_for_kai_form:
                        # Fallback manual jika locale Indonesia gagal atau strftime gagal
                        bulan_map_indonesia = {
                            1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
                            7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
                        }
                        date_str_for_kai_form = f"{current_date_obj.day:02d}-{bulan_map_indonesia[current_date_obj.month]}-{current_date_obj.year}"
                        print(f"  Menggunakan format tanggal manual (Indonesia): {date_str_for_kai_form}")
                    
                    print(f"  Scraping untuk tanggal kalender: {current_date_obj.strftime('%Y-%m-%d')}")

                    page_html, actual_url_loaded = scrape_kai_with_selenium(
                        driver, origin_name, dest_name, date_str_for_kai_form, 
                        adult_passengers, infant_passengers
                    )
                    
                    query_context = {
                        'query_origin_name': origin_name,
                        'query_origin_code': origin_code,
                        'query_destination_name': dest_name,
                        'query_destination_code': dest_code,
                        'query_date_calendar': current_date_obj.strftime('%Y-%m-%d'),
                        'query_date_input_format': date_str_for_kai_form
                    }

                    if page_html:
                        data_from_current_page = parse_schedule_html_content(page_html, actual_url_loaded or "N/A", query_context)
                        if data_from_current_page:
                            all_extracted_data.extend(data_from_current_page)
                    else:
                        print("    Tidak mendapatkan HTML dari Selenium untuk diproses.")
                    
                    print(f"  Menunggu {delay_between_searches} detik sebelum pencarian berikutnya...")
                    time.sleep(delay_between_searches)
    finally:
        if driver:
            print("Menutup WebDriver...")
            driver.quit()
            print("WebDriver berhasil ditutup.")

    if all_extracted_data:
        print(f"\nTotal {len(all_extracted_data)} jadwal kereta berhasil diekstrak dari semua query.")
        save_to_csv(all_extracted_data, csv_output_filename)
    else:
        print("\nTidak ada data jadwal kereta yang berhasil diekstrak dari semua query.")

    print("Proses scraping otomatis selesai.")

    # Contoh cara mengakses data spesifik:
    # if extracted_data:
    #     print(f"\nContoh Data Pertama:")
    #     print(f"Nama Kereta: {extracted_data[0].get('train_name')}") 
    #     print(f"Harga: {extracted_data[0].get('price')}")
    #     print(f"Trip ID: {extracted_data[0].get('hidden_details', {}).get('trip_id')}") 