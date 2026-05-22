import requests
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ================= HTTP =================
session = requests.Session()
session.headers.update(HEADERS)

def fetch_json(url):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return {}

# ================= STREAM CHECK =================
def is_working_m3u8(url):
    if ".m3u8" not in url:
        return False
    try:
        r = session.head(url, timeout=3)
        return r.status_code == 200
    except:
        return False

def is_valid_tv(url):
    if ".m3u8" not in url:
        return False
    if any(x in url for x in ["udp://", "rtp://"]):
        return False
    return True

def check_stream(url):
    if is_valid_tv(url):
        return url if is_working_m3u8(url) else None
    return None

# ================= PICK STREAM =================
def pick_stream(streams):
    m3u8_hd = None
    m3u8 = None
    for s in streams:
        name = s.get("name", "").upper()
        url = s.get("sourceUrl")
        if not url:
            continue
        if ".m3u8" in url:
            if "FHD" in name or "HD" in name:
                m3u8_hd = url
            else:
                m3u8 = url
    return m3u8_hd or m3u8

# ================= API STANDARD =================
def process_standard(url, group):
    out = []
    data = fetch_json(url)
    for item in data.get("data", []):
        dt = datetime.now()
        if item.get("startTime"):
            try:
                dt = datetime.strptime(item["startTime"][:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=7)
            except:
                pass
        for c in item.get("fixtureCommentators", []):
            comm = c.get("commentator", {})
            stream = pick_stream(comm.get("streams", []))
            if not stream:
                continue
            out.append({
                "time": dt,
                "group": group,
                "title": f'{dt.strftime("%H:%M")} | {item.get("title")}',
                "logo": item.get("homeTeam", {}).get("logoUrl", ""),
                "url": stream
            })
            break
    return out

# ================= VONG CAM =================
def process_vongcam():
    out = []
    data = fetch_json("https://sv.bugiotv.xyz/internal/api/matches")
    for item in data.get("data", []):
        url = item.get("commentator", {}).get("streamSourceFhd")
        if not url or ".m3u8" not in url:
            continue
        out.append({
            "time": datetime.now(),
            "group": "VÒNG CẤM TV",
            "title": item.get("title"),
            "logo": item.get("homeClub", {}).get("logoUrl", ""),
            "url": url
        })
    return out

# ================= CO LA =================
def process_cala_tv():
    out = []
    data = fetch_json("https://api.cltvlv.com/api/matches")
    for key, item in data.get("data", {}).items():
        dt = datetime.fromtimestamp(item.get("matchTime", datetime.now().timestamp()))
        home = item.get("home_team", {})
        away = item.get("away_team", {})
        streams = item.get("anchorAppointmentVoList", [])
        stream_url = None
        for s in streams:
            if s.get("playStreamAddress2") and ".m3u8" in s["playStreamAddress2"]:
                stream_url = s["playStreamAddress2"]
                break
        if not stream_url:
            continue
        out.append({
            "time": dt,
            "group": "CO LA TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logo", ""),
            "url": stream_url
        })
    return out

# ================= TAM QUOC =================
def process_tamquoc_tv():
    out = []
    data = fetch_json("https://sv.tamquoctv.xyz/internal/api/matches")
    items = data.get("data", [])
    if isinstance(items, dict):
        items = items.values()
    for item in items:
        dt = datetime.now()
        if item.get("startTime"):
            try:
                dt = datetime.strptime(item["startTime"][:19], "%Y-%m-%dT%H:%M:%S")
            except:
                pass
        home = item.get("homeClub", {})
        away = item.get("awayClub", {})
        commentator = item.get("commentator", {})
        stream_url = (
            commentator.get("streamSourceFhd")
            or commentator.get("streamSourceHd")
            or commentator.get("streamSourceSd")
        )
        if not stream_url or ".m3u8" not in stream_url:
            continue
        out.append({
            "time": dt,
            "group": "TAM QUOC TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logoUrl", ""),
            "url": stream_url
        })
    return out

# ================= CHUOI CHIEN TV =================
def get_chuoichien_token():
    data = fetch_json("https://api.chuoichientv.com/v1/encrypted/token")
    if data.get("success"):
        return data.get("token")
    return None

def process_chuoichien_tv():
    out = []
    token = get_chuoichien_token()
    if not token:
        print("Không lấy được token từ chuoichienTV")
        return out
    data = fetch_json("https://api-v2.chuoichientv.com/v2/matches?type=live&page=1&limit=1000")
    for item in data.get("matches", []):
        dt = datetime.now()
        if item.get("matchTime"):
            try:
                dt = datetime.strptime(item["matchTime"][:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=7)
            except:
                pass
        home = item.get("teams", {}).get("home", {})
        away = item.get("teams", {}).get("away", {})
        for group_key in ["blvs", "blvs_bonglau"]:
            for c in item.get(group_key, []):
                for s in c.get("streams", []):
                    url = s.get("url")
                    label = s.get("label", "").upper()
                    if url and url.endswith(".m3u8") and ("HD" in label or "FHD" in label):
                        url_with_headers = (
                            f'{url}|User-Agent=Mozilla/5.0&Referer=https://chuoichientv.com/&Authorization=Bearer {token}'
                        )
                        out.append({
                            "time": dt,
                            "group": "CHUOI CHIEN TV",
                            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
                            "logo": home.get("logo", ""),
                            "url": url_with_headers
                        })
    return out
# ================= LOAD FPT SPORT =================
def load_fpt_sport(url):
    out = []
    try:
        r = session.get(url, timeout=15)
        lines = r.text.splitlines()
        title = ""
        for line in lines:
            if line.startswith("#EXTINF"):
                title = line.split(",")[-1].strip()
            elif line.startswith("http"):
                out.append({
                    "time": datetime.now(),
                    "group": "FPT SPORT",
                    "title": title if title else "FPT SPORT",
                    "logo": "",
                    "url": line.strip()
                })
    except Exception as e:
        print(f"Error loading FPT Sport: {e}")
    return out
# ================= WRITE FILE =================

def write_files(data):
    seen = set()
    tv = "#EXTM3U\n"
    full = "#EXTM3U\n"

    items = []
    for item in data:
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        extinf = (
            f'#EXTINF:-1 group-title="{item["group"]}" '
            f'tvg-logo="{item["logo"]}",{item["title"]}\n'
        )
        items.append((extinf, url, item["group"]))

    # FULL: ghi tất cả
    for extinf, url, group in items:
        full += extinf + f"{url}\n\n"

    # TV FILTER: kiểm tra song song
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        for extinf, url, group in items:
            if group == "CHUOI CHIEN TV":
                # bỏ qua check_stream cho CHUOI CHIEN TV
                tv += extinf + f"{url}\n\n"
            else:
                futures[executor.submit(check_stream, url)] = (extinf, url)

        for future in as_completed(futures):
            result = future.result()
            if result:
                extinf, url = futures[future]
                tv += extinf + f"{url}\n\n"

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write(tv)
    with open("full.m3u", "w", encoding="utf-8") as f:
        f.write(full)

    print("DONE PRO MAX++ ✔")
    print(f"TV Channels: {tv.count('#EXTINF')}")
    print(f"FULL Channels: {full.count('#EXTINF')}")

# ================= CONVERT TO JSON=================
def write_json(data):
    output = {
        "id": "tonghop",
        "url": "https://tinyurl.com/thapcam",
        "name": "Tổng Hợp TV",
        "color": "#1cb57a",
        "grid_number": 3,
        "image": {
            "type": "cover",
            "url": "https://kaytee1012.github.io/hoiquan_logo.png"
        },
        "notice": {
            "closeable": True,
            "icon": "https://kaytee1012.github.io/pngegg.png",
            "id": "notice",
            "link": "https://t.me/dqstore1",
            "text": "Nhóm Tele"
        },
        "groups": []
    }

    groups_map = {}
    for item in data:
        group_id = item["group"]
        if group_id not in groups_map:
            groups_map[group_id] = {
                "id": group_id.lower().replace(" ", "-"),
                "name": f"🔴 {group_id}",
                "display": "vertical",
                "grid_number": 2,
                "enable_detail": False,
                "channels": []
            }

        # Xác định label: nếu có url thì Live, nếu không thì Chưa live
        label_text = "● Live" if item.get("url") else "⏳ Chưa live"
        label_color = "#ff0000" if item.get("url") else "#d54f1a"

        channel_id = f'{group_id}-{item["time"].strftime("%H%M%S")}'
        channel = {
            "id": channel_id,
            "name": f'⚽ {item["title"]}',
            "type": "single",
            "display": "thumbnail-only",
            "enable_detail": False,
            "image": {
                "padding": 1,
                "background_color": "#ececec",
                "display": "contain",
                "url": item["logo"],
                "width": 1600,
                "height": 1200
            },
            "labels": [{
                "text": label_text,
                "position": "top-left",
                "color": "#00ffffff",
                "text_color": label_color
            }],
            "sources": [{
                "id": channel_id,
                "name": group_id,
                "contents": [{
                    "id": channel_id,
                    "name": item["title"],
                    "streams": [{
                        "id": channel_id,
                        "name": "F",
                        "stream_links": [{
                            "id": "lnk-1",
                            "name": "Link 1",
                            "type": "hls",
                            "default": True,
                            "url": item["url"]
                        }] if item.get("url") else []
                    }]
                }]
            }]
        }

        groups_map[group_id]["channels"].append(channel)

    output["groups"] = list(groups_map.values())

    with open("tonghop.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("JSON file channels.json đã được tạo ✔")

# ================= MAIN =================
if __name__ == "__main__":
    data = []
    # HỘI QUÁN
    data += process_standard("https://sv.hoiquantv.xyz/api/v1/external/fixtures/unfinished", "HỘI QUÁN")
    # THIÊN ĐÌNH
    data += process_standard("https://sv.thiendinhtv.xyz/api/v1/external/fixtures/unfinished", "THIÊN ĐÌNH")
    # XAY CON
    data += process_standard("https://sv.xaycontv.xyz/api/v1/external/fixtures/unfinished", "XAY CON")
    # VÒNG CẤM
    data += process_vongcam()
    # CO LA TV
    data += process_cala_tv()
    # TAM QUOC TV
    data += process_tamquoc_tv()
    # CHUOI CHIEN TV
    data += process_chuoichien_tv()
    # FPT SPORT
    data += load_fpt_sport("https://raw.githubusercontent.com/t23-02/bongda/refs/heads/main/bongda.m3u")
    # WRITE
    write_files(data)
    write_json(data)
