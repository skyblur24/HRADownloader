#!/usr/bin/env python3

# Standard
import os
import re
import sys
import json
import time
import platform
import traceback

# Third party
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup, NavigableString, Tag

# ==========================================
# 🔧 DOWNLOAD PATH
# ==========================================
BASE_DOWNLOAD_PATH = "/content/drive/MyDrive/HIGHRESAUDIO/"
# ==========================================

# ==========================================
# ⚙️ DL OPTIONS
# ==========================================
DOWNLOAD_ALBUM_COVER = True
DOWNLOAD_PLAYLIST = False
DOWNLOAD_INFO = True
DOWNLOAD_BIOGRAPHY = False
DOWNLOAD_FACEBOOK_GROUPS = False
SPLIT_INTO_SUBALBUM_FOLDERS = True
# ==========================================

# ==========================================
# 📢 .TXT
# ==========================================
FACEBOOK_GROUPS_TEXT = """Music Hi-Res: FLAC, ALAC, WAV, AIFF, DSD, MQA:
1) https://www.facebook.com/share/g/1GmBC2S3L9/

Hi-Res Music COLLECTIONS
2) https://www.facebook.com/groups/5788529257834095/?ref=share&mibextid=NSMWBT

Hi-Res Music 2.0
3) https://www.facebook.com/groups/1387967035816889/?ref=share&mibextid=NSMWBT

Hi-Res México 
4) https://www.facebook.com/groups/250689829912723/?ref=share&mibextid=NSMWBT"""
# ==========================================

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
})

def getOs():
    return platform.system() == 'Windows'

def osCommands(x):
    if getOs():
        if x == "p":
            os.system('pause >nul')
        elif x == "c":
            os.system('cls')
        elif x == "t":
            os.system('title HRA-DL (Optimized)')
    else:
        if x == "p":
            os.system("read -rsp $''")
        elif x == "c":
            os.system('clear')
        elif x == "t":
            sys.stdout.write("\x1b]2;HRA-DL (Optimized)\x07")

def login(email, pwd):
    r = session.get(
        f'https://streaming.highresaudio.com:8182/vault3/user/login?password={pwd}&username={email}'
    )
    if r.status_code == 200 and "has_subscription" in r.json():
        print("Signed in successfully.\n")
        return r.text
    else:
        print("Login failed or no subscription.")
        osCommands('p')
        sys.exit()

def fetchAlbumId(url):
    soup = BeautifulSoup(session.get(url).text, "html.parser")
    return soup.find(attrs={"data-id": True})['data-id']

def fetchMetadata(albumId, userData):
    r = session.get(
        f'https://streaming.highresaudio.com:8182/vault3/vault/album/?album_id={albumId}&userData={userData}'
    )
    if r.status_code != 200:
        print("Failed to fetch metadata.")
        osCommands('p')
        sys.exit()
    return r.json()

def dirSetup(path):
    os.makedirs(path, exist_ok=True)
    return path

def fileSetup(fname):
    if os.path.isfile(fname):
        os.remove(fname)

# ==========================================
# 📄 Playlist
# ==========================================
def fetchPlaylistGroups(url):
    soup = BeautifulSoup(session.get(url).text, "html.parser")

    playlist_div = soup.find(id="albumtab-playlist")
    if not playlist_div:
        return None

    items = playlist_div.find_all("li")
    if not items:
        return None

    groups = []
    current = {"name": None, "tracks": []}

    for li in items:
        classes = li.get("class", [])

        if "plinfo" in classes:
            if current["tracks"] or current["name"] is not None:
                groups.append(current)
            name = li.get_text(strip=True).rstrip(":").strip()
            current = {"name": name, "tracks": []}

        elif "pltrack" in classes:
            nr = li.get("data-nr")
            title_span = li.find("span", class_="title")
            title = title_span.get_text(strip=True) if title_span else ""
            current["tracks"].append((int(nr) if nr and nr.isdigit() else None, title))

    if current["tracks"]:
        groups.append(current)

    return groups if groups else None

def save_tracklist(groups, albumPath):
    tracklist_path = os.path.join(albumPath, "Playlist.txt")
    lines = []
    counter = 0
    for g in groups:
        if g["name"]:
            lines.append(f"{g['name']}:")
        for orig_num, title in g["tracks"]:
            counter += 1
            number = orig_num if orig_num is not None else counter
            lines.append(f"{number:02d} {title}")
        lines.append("")

    with open(tracklist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

# ==========================================
# 📝 INFO
# ==========================================
HEADING_TAGS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
BLOCK_TAGS = ('p', 'div', 'li') + HEADING_TAGS

BOLD_MAP = {}
for _i in range(26):
    BOLD_MAP[chr(ord('A') + _i)] = chr(0x1D63C + _i)  # 𝘼-𝙕
    BOLD_MAP[chr(ord('a') + _i)] = chr(0x1D656 + _i)  # 𝙖-𝙯
for _i in range(10):
    BOLD_MAP[chr(ord('0') + _i)] = chr(0x1D7EC + _i)  # 𝟬-𝟵

def toBold(text):
    return "".join(BOLD_MAP.get(ch, ch) for ch in text)

REVERSE_BOLD_MAP = {v: k for k, v in BOLD_MAP.items()}

def unbold(text):
    return "".join(REVERSE_BOLD_MAP.get(ch, ch) for ch in text)

BOLD_CHARS = set(BOLD_MAP.values())

def is_bold_line(line):
    chars = [c for c in line if c.isalnum()]
    if not chars:
        return False
    return all(c in BOLD_CHARS for c in chars)

def render_node(el, output):
    if isinstance(el, NavigableString):
        output.append(str(el))
        return
    if not isinstance(el, Tag):
        return
    name = el.name

    if name in ('script', 'style'):
        return

    if name in ('strong', 'b'):
        temp = []
        for child in el.children:
            render_node(child, temp)
        output.append(toBold("".join(temp)))
        return

    if name == 'br':
        output.append("\n")
        return

    if name in HEADING_TAGS:
        temp = []
        for child in el.children:
            render_node(child, temp)
        output.append("\n")
        output.append(toBold("".join(temp)))
        output.append("\n")
        return

    if name in BLOCK_TAGS:
        output.append("\n")
        for child in el.children:
            render_node(child, output)
        output.append("\n")
        return

    for child in el.children:
        render_node(child, output)

def formatText(div, skip_label=None):
    output = []
    for child in div.children:
        render_node(child, output)
    raw = "".join(output)

    # Limpiar espacios dentro de cada línea sin perder los saltos de párrafo
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in raw.split("\n")]

    cleaned = []
    prev_blank = True
    for line in lines:
        if line == "":
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    # Quitar la etiqueta de pestaña duplicada al inicio (p. ej. "Info" suelto antes de "Info for ...")
    if skip_label and cleaned and cleaned[0].strip().lower() == skip_label.lower():
        cleaned = cleaned[1:]
        while cleaned and cleaned[0] == "":
            cleaned = cleaned[1:]

    return "\n".join(cleaned).strip()

def fetchInfo(url):
    soup = BeautifulSoup(session.get(url).text, "html.parser")

    info_div = soup.find(id="albumtab-info")
    info_text = formatText(info_div, skip_label="Info") if info_div else "No info found."

    return info_text

def save_info(info_text, albumPath):
    info_path = os.path.join(albumPath, "Info.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(info_text)

# ==========================================
# 🔥 Anti-Cld
# ==========================================
def fetchTrack(albumId, fname, spec, trackNum, trackTitle, trackTotal, url):
    max_retries = 6
    timeout_seconds = 8
    attempt = 0

    while attempt < max_retries:
        try:
            session.headers.update({
                "range": "bytes=0-",
                "referer": f"https://stream-app.highresaudio.com/album/{albumId}"
            })

            print(f"Downloading {trackNum}/{trackTotal}: {trackTitle} - {spec}")

            r = session.get(url, stream=True, timeout=15)
            size = int(r.headers.get('content-length', 0))

            downloaded = 0
            last_progress_time = time.time()

            with open(fname, 'wb') as f:
                with tqdm(total=size, unit='B', unit_scale=True, unit_divisor=1024) as bar:
                    for chunk in r.iter_content(128 * 1024):
                        if chunk:
                            f.write(chunk)
                            chunk_size = len(chunk)
                            downloaded += chunk_size
                            bar.update(chunk_size)
                            last_progress_time = time.time()

                        if time.time() - last_progress_time > timeout_seconds:
                            raise Exception("Download stalled")

            return  # Success

        except Exception:
            attempt += 1
            print(f"\n⚠ Download interrupted. Retrying... ({attempt}/{max_retries})\n")
            time.sleep(2)

    print(f"\n❌ Failed after {max_retries} attempts.\n")

def fetchFile(url, dest):
    fileSetup(dest)
    r = session.get(url, stream=True)
    size = int(r.headers.get('content-length', 0))

    with open(dest, 'wb') as f:
        with tqdm(total=size, unit='B', unit_scale=True, unit_divisor=1024) as bar:
            for chunk in r.iter_content(128 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

def forceRegionEn(url):
    return re.sub(r'(highresaudio\.com/)[a-z]{2}(/album/view/)', r'\1en\2', url)

def fetchBiography(url):
    soup = BeautifulSoup(session.get(url).text, "html.parser")

    bio_div = soup.find(id="albumtab-biography")
    if not bio_div:
        return None

    bio_text = formatText(bio_div, skip_label="Biography")

    # Quitar placeholders vacíos (ej. "prices") que quedan antes del texto real
    lines = bio_text.split("\n")
    while lines and lines[0].strip().lower() in ("", "prices"):
        lines.pop(0)
    bio_text = "\n".join(lines).strip()

    return bio_text if bio_text else None

def save_biography(bio_text, albumPath):
    bio_path = os.path.join(albumPath, "Biography.txt")
    with open(bio_path, "w", encoding="utf-8") as f:
        f.write(bio_text)

def save_facebook_groups(albumPath):
    fb_path = os.path.join(albumPath, "Music Hi-Res.txt")
    with open(fb_path, "w", encoding="utf-8") as f:
        f.write(FACEBOOK_GROUPS_TEXT)

def sanitizeFname(fname):
    if getOs():
        return re.sub(r'[\\/:*?"><|]', '-', fname)
    else:
        return re.sub('/', '-', fname)

def main(userData):
    url = input("Input HIGHRESAUDIO Store URL: ").strip()

    if not url:
        osCommands('c')
        return

    if not re.match(r"https?://(?:www\.)?highresaudio\.com/", url):
        print("Invalid URL.")
        time.sleep(1)
        osCommands('c')
        return

    url = forceRegionEn(url)

    osCommands('c')

    albumId = fetchAlbumId(url)
    metadata = fetchMetadata(albumId, userData)

    artist = metadata['data']['results']['artist']
    title = metadata['data']['results']['title']
    tracks = metadata['data']['results']['tracks']

    # ==========================================
    # 🔎 DETECTAR CALIDAD (Sample Rates)
    # ==========================================
    sample_rates = set()
    for t in tracks:
        try:
            rate = float(t['format'])
            sample_rates.add(rate)
        except:
            pass

    sample_rates = sorted(sample_rates)
    formatted_rates = [f"{r:.1f}kHz" if r % 1 == 0 else f"{r}kHz" for r in sample_rates]
    rate_string = " & ".join(formatted_rates)
    quality_tag = f"[HIGHRESAUDIO HRA 24bits/{rate_string}]"

    # ==========================================
    # 📘 BOOKLET
    # ==========================================
    hasBooklet = "booklet" in metadata['data']['results']
    if hasBooklet:
        albumFolder = f"{artist} - {title} {quality_tag} + Digital Booklet"
    else:
        albumFolder = f"{artist} - {title} {quality_tag}"

    print(f"{albumFolder}\n")

    albumPath = dirSetup(
        os.path.join(BASE_DOWNLOAD_PATH, sanitizeFname(albumFolder))
    )

    # Generar Tracklist (y detectar sub-álbumes)
    groups = fetchPlaylistGroups(url)

    if not groups:
        groups = [{"name": None, "tracks": [(t['trackNumber'], t['title']) for t in tracks]}]

    if DOWNLOAD_PLAYLIST:
        save_tracklist(groups, albumPath)

    # Generar Info
    if DOWNLOAD_INFO:
        info_text = fetchInfo(url)
        save_info(info_text, albumPath)

    # Generar Biography (solo si el álbum tiene una disponible)
    if DOWNLOAD_BIOGRAPHY:
        bio_text = fetchBiography(url)
        if bio_text:
            save_biography(bio_text, albumPath)
        else:
            print("No Biography available for this album.")

    # Grupos de Facebook
    if DOWNLOAD_FACEBOOK_GROUPS:
        save_facebook_groups(albumPath)

    # ==========================================
    # 🎨 DOWNLOAD Cover
    # ==========================================
    cover_data = metadata['data']['results'].get("cover")
    if DOWNLOAD_ALBUM_COVER and cover_data:
        if "master" in cover_data and "file_url" in cover_data["master"]:
            print("Downloading Folder...")
            cover_url = "https://" + cover_data["master"]["file_url"]
            coverFname = sanitizeFname(title) + ".jpg"
            fetchFile(cover_url, os.path.join(albumPath, coverFname))

    if SPLIT_INTO_SUBALBUM_FOLDERS and len(groups) > 1 and sum(len(g["tracks"]) for g in groups) == len(tracks):
        sorted_tracks = sorted(tracks, key=lambda t: t['trackNumber'])
        idx = 0

        for g in groups:
            group_name_plain = unbold(g["name"]) if g["name"] else "Tracks"
            groupPath = dirSetup(os.path.join(albumPath, sanitizeFname(group_name_plain)))

            n = len(g["tracks"])
            group_tracks = sorted_tracks[idx:idx + n]
            group_nums = [num for num, _ in g["tracks"]]
            idx += n
            groupTotal = str(len(tracks)).zfill(2)

            for i, track in enumerate(group_tracks):
                page_num = group_nums[i] if group_nums[i] is not None else track['trackNumber']
                trackNum = str(page_num).zfill(2)
                trackTitle = sanitizeFname(track['title'])

                tempFile = os.path.join(groupPath, f"{trackNum}.flac")
                finalFile = os.path.join(groupPath, f"{trackNum}. {trackTitle}.flac")

                fileSetup(tempFile)
                fileSetup(finalFile)

                fetchTrack(
                    albumId,
                    tempFile,
                    f"{track['format']} kHz FLAC",
                    trackNum,
                    track['title'],
                    groupTotal,
                    track['url']
                )

                if os.path.exists(tempFile):
                    os.rename(tempFile, finalFile)
    else:
        totalTracks = str(len(tracks)).zfill(2)

        for track in tracks:
            trackNum = str(track['trackNumber']).zfill(2)
            trackTitle = sanitizeFname(track['title'])

            tempFile = os.path.join(albumPath, f"{trackNum}.flac")
            finalFile = os.path.join(albumPath, f"{trackNum}. {trackTitle}.flac")

            fileSetup(tempFile)
            fileSetup(finalFile)

            fetchTrack(
                albumId,
                tempFile,
                f"{track['format']} kHz FLAC",
                trackNum,
                track['title'],
                totalTracks,
                track['url']
            )

            if os.path.exists(tempFile):
                os.rename(tempFile, finalFile)

    # ==========================================
    # 📘 booklet DOWNLOAD
    # ==========================================
    if hasBooklet:
        print("Downloading Digital Booklet...")
        fetchFile(
            f"https://{metadata['data']['results']['booklet']}",
            os.path.join(albumPath, "booklet.pdf")
        )

    print("\nAlbum completed.")
    time.sleep(1)
    osCommands('c')

if __name__ == '__main__':
    osCommands('t')

    with open("config.json") as f:
        config = json.load(f)

    userData = login(config["email"], config["password"])

    try:
        while True:
            main(userData)
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
    except:
        traceback.print_exc()
        input("\nAn exception has occurred. Press enter to exit.")
        sys.exit()