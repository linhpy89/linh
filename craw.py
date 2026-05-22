import requests
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ================= HTTP =================
session = requests.Session()
session.headers.update(HEADERS)

def fetch_json(url):
    try:
        r = session.get(url, timeout=12) # Tăng timeout lên 12s để tránh mất cấu trúc API khi mạng chậm
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[-] Error fetching JSON from {url}: {e}")
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

def check_stream(item):
    url = item.get("url", "")
    if item["group"] == "CHUOI CHIEN TV":
        return item
    
    if is_valid_tv(url) and is_working_m3u8(url):
        return item
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
            
            blv_name = comm.get("name") or "Đang cập nhật"
            out.append({
                "time": dt,
                "group": group,
                "title": f'{dt.strftime("%H:%M")} | {item.get("title")}',
                "logo": item.get("homeTeam", {}).get("logoUrl", ""),
                "url": stream,
                "commentator": blv_name
            })
            break
    return out

# ================= VONG CAM =================
def process_vongcam():
    out = []
    data = fetch_json("https://sv.bugiotv.xyz/internal/api/matches")
    for item in data.get("data", []):
        comm = item.get("commentator", {})
        url = comm.get("streamSourceFhd")
        if not url or ".m3u8" not in url:
            continue
        
        blv_name = comm.get("name") or "VÒNG CẤM TV"
        out.append({
            "time": datetime.now(),
            "group": "VÒNG CẤM TV",
            "title": item.get("title"),
            "logo": item.get("homeClub", {}).get("logoUrl", ""),
            "url": url,
            "commentator": blv_name
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
        blv_name = "CO LA TV"
        
        for s in streams:
            if s.get("playStreamAddress2") and ".m3u8" in s["playStreamAddress2"]:
                stream_url = s["playStreamAddress2"]
                blv_name = s.get("nickName") or "CO LA TV"
                break
        if not stream_url:
            continue
            
        out.append({
            "time": dt,
            "group": "CO LA TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logo", ""),
            "url": stream_url,
            "commentator": blv_name
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
            
        blv_name = commentator.get("name") or "TAM QUOC TV"
        out.append({
            "time": dt,
            "group": "TAM QUOC TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logoUrl", ""),
            "url": stream_url,
            "commentator": blv_name
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
                blv_name = c.get("name") or "CHUOI CHIEN TV"
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
                            "url": url_with_headers,
                            "commentator": blv_name
                        })
    return out

# ================= LOAD FPT SPORT =================
def load_fpt_sport(url):
    out = []
    try:
        r = session.get(url, timeout=10)
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
                    "url": line.strip(),
                    "commentator": "FPT SPORT"
                })
    except Exception as e:
        print(f"Error loading FPT Sport: {e}")
    return out

# ================= WRITE M3U FILES =================
def write_m3u_files(full_data, working_data):
    full_m3u = "#EXTM3U\n"
    tv_m3u = "#EXTM3U\n"

    for item in full_data:
        full_m3u += f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}",{item["title"]}\n{item["url"]}\n\n'

    for item in working_data:
        tv_m3u += f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}",{item["title"]}\n{item["url"]}\n\n'

    with open("full.m3u", "w", encoding="utf-8") as f:
        f.write(full_m3u)
    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write(tv_m3u)

    print(f"[+] M3U Exported - Full: {len(full_data)} channels | Live TV: {len(working_data)} channels")

# ================= CONVERT TO JSON (FIXED ORDER) =================
def write_json(valid_data):
    output = {
        "id": "channels",
        "url": "https://vanlinh.io.vn",
        "name": "VLINH-TV",
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
            "link": "https://t.me/",
            "text": "Nhóm Tele"
        },
        "groups": []
    }

    # ĐỊNH NGHĨA THỨ TỰ NHÓM XUẤT HIỆN THEO ĐÚNG Ý BẠN
    # Bạn muốn đưa nhà đài nào lên trước chỉ cần thay đổi vị trí chuỗi trong list này:
    ORDERED_GROUPS = [
        "HỘI QUÁN",
        "XAY CON",
        "THIÊN ĐÌNH",
        "VÒNG CẤM TV",
        "TAM QUỐC TV",
        "COLA TV",
        "CHUOICHIEN TV",
        "FPT SPORT"
    ]

    groups_map = {}
    # Khởi tạo sẵn cấu trúc group dựa trên danh sách thứ tự cố định ở trên
    for group_id in ORDERED_GROUPS:
        groups_map[group_id] = {
            "id": group_id.lower().replace(" ", "-"),
            "name": f"🔴 {group_id}",
            "display": "vertical",
            "grid_number": 2,
            "enable_detail": False,
            "channels": []
        }

    for item in valid_data:
        group_id = item["group"]
        
        # Nếu có group lạ nằm ngoài danh sách định sẵn thì tạo mới tạm thời ở dưới cùng
        if group_id not in groups_map:
            groups_map[group_id] = {
                "id": group_id.lower().replace(" ", "-"),
                "name": f"🔴 {group_id}",
                "display": "vertical",
                "grid_number": 2,
                "enable_detail": False,
                "channels": []
            }

        label_text = "● Live" if item.get("url") else "⏳ Chưa live"
        label_color = "#ff0000" if item.get("url") else "#d54f1a"
        channel_id = f'{group_id}-{item["time"].strftime("%H%M%S")}'
        blv_display_name = item.get("commentator", "Đang Live")

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
                        "name": blv_display_name,
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

    # Lọc bỏ các group trống (không cào được trận nào tại thời điểm chạy) để file JSON luôn sạch
    final_groups = []
    for group_id in ORDERED_GROUPS:
        if groups_map[group_id]["channels"]:
            final_groups.append(groups_map[group_id])
            
    # Thêm nốt các group phát sinh (nếu có)
    for group_id, group_data in groups_map.items():
        if group_id not in ORDERED_GROUPS and group_data["channels"]:
            final_groups.append(group_data)

    output["groups"] = final_groups

    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("[+] JSON file channels.json đã được thiết lập đúng thứ tự ưu tiên ✔")

# ================= MAIN =================
if __name__ == "__main__":
    start_time = datetime.now()
    raw_data = []
    
    tasks = [
        (process_standard, "https://sv.hoiquantv.xyz/api/v1/external/fixtures/unfinished", "HỘI QUÁN"),
        (process_standard, "https://sv.thiendinhtv.xyz/api/v1/external/fixtures/unfinished", "THIÊN ĐÌNH"),
        (process_standard, "https://sv.xaycontv.xyz/api/v1/external/fixtures/unfinished", "XAY CON"),
        (process_vongcam,),
        (process_cala_tv,),
        (process_tamquoc_tv,),
        (process_chuoichien_tv,),
        (load_fpt_sport, "https://raw.githubusercontent.com/t23-02/bongda/refs/heads/main/bongda.m3u")
    ]
    
    print("[*] Đang cào dữ liệu song song từ các API...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_api = []
        for task in tasks:
            func = task[0]
            args = task[1:]
            future_to_api.append(executor.submit(func, *args))
            
        for future in as_completed(future_to_api):
            try:
                res = future.result()
                if res:
                    raw_data.extend(res)
            except Exception as e:
                print(f"[-] Lỗi luồng cào dữ liệu: {e}")

    seen_urls = set()
    unique_raw_data = []
    for item in raw_data:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_raw_data.append(item)

    print(f"[*] Đang kiểm tra trạng thái hoạt động của {len(unique_raw_data)} streams...")
    working_data = []
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        future_to_check = {executor.submit(check_stream, item): item for item in unique_raw_data}
        for future in as_completed(future_to_check):
            result = future.result()
            if result:
                working_data.append(result)

    write_m3u_files(unique_raw_data, working_data)
    write_json(working_data)

    print(f"DONE PRO MAX++ ✔ | Tổng thời gian thực thi: {(datetime.now() - start_time).total_seconds():.2f} giây")
