import requests
import re
import json
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

session = requests.Session()
session.headers.update(HEADERS)

def fetch_json(url):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}

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
        
        # Bóc tách tất cả các BLV/Đường truyền thay vì chỉ lấy 1 cái đầu tiên
        streams_list = []
        for idx, c in enumerate(item.get("fixtureCommentators", [])):
            comm = c.get("commentator", {})
            stream_url = pick_stream(comm.get("streams", []))
            if stream_url:
                blv_name = comm.get("name", f"Server {idx + 1}")
                streams_list.append({
                    "url": stream_url,
                    "name": blv_name
                })

        if streams_list:
            out.append({
                "name": f'{dt.strftime("%H:%M")} | {item.get("title")}',
                "group": group,
                "streams": streams_list
            })
    return out

def process_vongcam():
    out = []
    data = fetch_json("https://sv.bugiotv.xyz/internal/api/matches")
    for item in data.get("data", []):
        url = item.get("commentator", {}).get("streamSourceFhd")
        if not url or ".m3u8" not in url:
            continue
        out.append({
            "name": item.get("title"),
            "group": "VÒNG CẤM TV",
            "streams": [{"url": url, "name": "Link 1"}]
        })
    return out

def load_external_keep_group(url):
    out = []
    try:
        r = session.get(url, timeout=15)
        lines = r.text.splitlines()
        title, group = "", "OTHER"
        for line in lines:
            if line.startswith("#EXTINF"):
                title = line.split(",")[-1].strip()
                m_group = re.search(r'group-title="([^"]+)"', line)
                group = m_group.group(1) if m_group else "OTHER"
            elif line.startswith("http") and ".m3u8" in line:
                out.append({
                    "name": title,
                    "group": group,
                    "streams": [{"url": line.strip(), "name": "Link Gốc"}]
                })
    except:
        pass
    return out

def load_fpt_sport(url):
    out = []
    try:
        r = session.get(url, timeout=15)
        lines = r.text.splitlines()
        title = ""
        for line in lines:
            if line.startswith("#EXTINF"):
                title = line.split(",")[-1].strip()
            elif line.startswith("http") and ".m3u8" in line:
                out.append({
                    "name": title if title else "FPT SPORT",
                    "group": "FPT SPORT",
                    "streams": [{"url": line.strip(), "name": "Link 1"}]
                })
    except:
        pass
    return out

# ================= ĐOẠN THAY ĐỔI: XUẤT RA JSON PHẲNG =================
def write_json_file(data, filename="channels.json"):
    # Gộp tất cả các trận đấu vào một cấu trúc chuẩn: { "channels": [ ... ] }
    output_data = {
        "channels": data
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"🎉 ĐÃ XUẤT JSON THÀNH CÔNG -> {filename}")
    print(f"Tổng số trận/kênh quét được: {len(data)}")

if __name__ == "__main__":
    all_channels = []

    # 1. Cào dữ liệu từ các nguồn API / Playlist
    all_channels += process_standard("https://sv.hoiquantv.xyz/api/v1/external/fixtures/unfinished", "HỘI QUÁN")
    all_channels += process_standard("https://sv.thiendinhtv.xyz/api/v1/external/fixtures/unfinished", "THIÊN ĐÌNH")
    all_channels += process_vongcam()
    all_channels += load_external_keep_group("https://raw.githubusercontent.com/hieu-TQS/TV/refs/heads/main/TV.m3u")
    all_channels += load_fpt_sport("https://raw.githubusercontent.com/t23-02/bongda/refs/heads/main/bongda.m3u")

    # 2. Xuất dữ liệu ra file channels.json thay vì file .m3u
    write_json_file(all_channels)