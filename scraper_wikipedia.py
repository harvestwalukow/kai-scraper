'''
Script untuk scraping data stasiun kereta api dari file Wikipedia HTML
dan menyimpannya dalam format tuple Python.
'''
from bs4 import BeautifulSoup
import re

def scrape_stations_from_html(html_file_path):
    '''
    Membaca file HTML Wikipedia dan mengekstrak nama stasiun beserta kodenya.
    
    Args:
        html_file_path (str): Path ke file HTML Wikipedia
        
    Returns:
        list: List of tuples (nama_stasiun, kode_stasiun)
    '''
    stations = []
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{html_file_path}' tidak ditemukan.")
        return stations
    except Exception as e:
        print(f"Error saat membaca file: {e}")
        return stations
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Cari tabel yang berisi data stasiun
    # Biasanya Wikipedia menggunakan tabel dengan class wikitable
    tables = soup.find_all('table', class_='wikitable')
    
    print(f"Ditemukan {len(tables)} tabel wikitable")
    
    for table_idx, table in enumerate(tables):
        print(f"\nMemproses tabel ke-{table_idx + 1}...")
        
        # Cari header tabel untuk menentukan kolom mana yang berisi nama dan kode stasiun
        headers = []
        header_row = table.find('tr')
        if header_row:
            for th in header_row.find_all(['th', 'td']):
                headers.append(th.get_text(strip=True).lower())
        
        print(f"Header tabel: {headers}")
        
        # Tentukan indeks kolom untuk nama dan kode stasiun
        name_col_idx = None
        code_col_idx = None
        
        # Cari kolom yang kemungkinan berisi nama stasiun
        for idx, header in enumerate(headers):
            if any(keyword in header for keyword in ['stasiun', 'station', 'nama', 'name']):
                if name_col_idx is None:  # Ambil yang pertama ditemukan
                    name_col_idx = idx
                    print(f"Kolom nama stasiun ditemukan di indeks {idx}: '{headers[idx]}'")
        
        # Cari kolom yang kemungkinan berisi kode stasiun
        for idx, header in enumerate(headers):
            if any(keyword in header for keyword in ['kode', 'code', 'singkatan', 'abbreviation']):
                code_col_idx = idx
                print(f"Kolom kode stasiun ditemukan di indeks {idx}: '{headers[idx]}'")
                break
        
        # Jika tidak ditemukan header yang jelas, coba heuristic berdasarkan isi
        if name_col_idx is None or code_col_idx is None:
            print("Header tidak jelas, mencoba analisis berdasarkan isi...")
            
            # Analisis beberapa baris data untuk menentukan kolom
            sample_rows = table.find_all('tr')[1:6]  # Ambil 5 baris pertama (skip header)
            for row in sample_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    for idx, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        
                        # Heuristic untuk kolom kode: teks pendek (2-5 karakter), huruf kapital
                        if len(text) >= 2 and len(text) <= 5 and text.isupper() and code_col_idx is None:
                            code_col_idx = idx
                            print(f"Kemungkinan kolom kode di indeks {idx} berdasarkan isi: '{text}'")
                        
                        # Heuristic untuk kolom nama: teks lebih panjang, mengandung kata "stasiun" atau nama kota
                        elif len(text) > 5 and name_col_idx is None:
                            if any(keyword in text.lower() for keyword in ['stasiun', 'station']) or text.istitle():
                                name_col_idx = idx
                                print(f"Kemungkinan kolom nama di indeks {idx} berdasarkan isi: '{text}'")
                
                if name_col_idx is not None and code_col_idx is not None:
                    break
        
        # Ekstrak data dari tabel jika kolom sudah diidentifikasi
        if name_col_idx is not None and code_col_idx is not None:
            print(f"Mengekstrak data: Nama di kolom {name_col_idx}, Kode di kolom {code_col_idx}")
            
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) > max(name_col_idx, code_col_idx):
                    name = cells[name_col_idx].get_text(strip=True)
                    code = cells[code_col_idx].get_text(strip=True)
                    
                    # Bersihkan nama stasiun
                    name = clean_station_name(name)
                    code = clean_station_code(code)
                    
                    if name and code and len(code) <= 6:  # Filter kode yang terlalu panjang
                        stations.append((name, code))
                        print(f"  Ditambahkan: {name} -> {code}")
        else:
            print(f"Tidak dapat mengidentifikasi kolom nama dan kode pada tabel ke-{table_idx + 1}")
    
    # Jika tidak ada tabel wikitable, coba cari pola lain
    if not stations:
        print("\nTidak ditemukan data dari tabel wikitable, mencoba pola lain...")
        
        # Cari list atau paragraf yang mungkin berisi data stasiun
        # Pola: "Nama Stasiun (KODE)" atau "Nama Stasiun - KODE"
        text_content = soup.get_text()
        
        # Pattern untuk mencari nama stasiun dengan kode
        patterns = [
            r'([A-Z][a-zA-Z\s]+(?:STASIUN|Stasiun)?)\s*[\(\-]\s*([A-Z]{2,5})\s*[\)]?',
            r'([A-Z][a-zA-Z\s]+)\s*[\(\-]\s*([A-Z]{2,5})\s*[\)]?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                name = clean_station_name(match[0])
                code = clean_station_code(match[1])
                if name and code:
                    stations.append((name, code))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_stations = []
    for station in stations:
        if station not in seen:
            seen.add(station)
            unique_stations.append(station)
    
    return unique_stations

def clean_station_name(name):
    '''Membersihkan nama stasiun dari karakter yang tidak diinginkan.'''
    if not name:
        return ""
    
    # Hapus kata "Stasiun" di awal atau akhir
    name = re.sub(r'^(Stasiun\s+|STASIUN\s+)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(\s+Stasiun|\s+STASIUN)$', '', name, flags=re.IGNORECASE)
    
    # Bersihkan karakter khusus
    name = re.sub(r'[^\w\s]', '', name)
    
    # Normalize spacing
    name = ' '.join(name.split())
    
    # Convert to title case
    name = name.upper()
    
    return name.strip()

def clean_station_code(code):
    '''Membersihkan kode stasiun dari karakter yang tidak diinginkan.'''
    if not code:
        return ""
    
    # Hapus karakter non-alphanumeric
    code = re.sub(r'[^A-Z0-9]', '', code.upper())
    
    return code.strip()

def save_stations_to_file(stations, output_file):
    '''Menyimpan data stasiun ke file dalam format tuple Python.'''
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for name, code in stations:
                f.write(f'("{name}", "{code}"),\n')
        print(f"\nData berhasil disimpan ke '{output_file}'")
        print(f"Total stasiun: {len(stations)}")
    except Exception as e:
        print(f"Error saat menyimpan file: {e}")

if __name__ == '__main__':
    # Konfigurasi
    html_input_file = 'wikipedia.html'
    txt_output_file = 'stasiun.txt'
    
    print("Memulai scraping data stasiun dari Wikipedia HTML...")
    print(f"File input: {html_input_file}")
    print(f"File output: {txt_output_file}")
    
    # Scrape data stasiun
    stations = scrape_stations_from_html(html_input_file)
    
    if stations:
        print(f"\nBerhasil mengekstrak {len(stations)} stasiun:")
        for i, (name, code) in enumerate(stations[:10], 1):  # Tampilkan 10 pertama
            print(f"  {i}. {name} -> {code}")
        
        if len(stations) > 10:
            print(f"  ... dan {len(stations) - 10} stasiun lainnya")
        
        # Simpan ke file
        save_stations_to_file(stations, txt_output_file)
    else:
        print("\nTidak ada data stasiun yang berhasil diekstrak.")
        print("Kemungkinan penyebab:")
        print("- Format tabel di HTML berbeda dari yang diharapkan")
        print("- Tidak ada tabel dengan class 'wikitable'")
        print("- Struktur data berbeda dari pola yang dicari")
        
    print("\nProses scraping selesai.")
