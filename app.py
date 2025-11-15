import streamlit as st
import requests
import re
import urllib.parse

st.set_page_config(page_title="夸克直链解析", layout="centered")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
share_pattern = re.compile(r"^https?://pan\.quark\.cn/s/([A-Za-z0-9]+)(?:\?pwd=([A-Za-z0-9]+))?$")

def fetch_share_page(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"访问分享页失败: HTTP {r.status_code}")
    return r.text

def extract_share_info(html: str):
    info = {"title": None, "share_id": None, "files": []}
    m_title = re.search(r"<title>(.*?)</title>", html, flags=re.S | re.I)
    if m_title:
        info["title"] = re.sub(r"\s+", " ", m_title.group(1)).strip()
    m_share = re.search(r"shareId\"?\s*[:=]\s*\"?(\d+)\"?", html)
    if m_share:
        info["share_id"] = m_share.group(1)
    file_entries = []
    for m in re.finditer(r"\{[^{}]*?\"fid\":\s*\"?(\d+)\"?[^{}]*?\"file_name\":\s*\"([^\"]+)\"", html):
        file_entries.append({"fid": m.group(1), "name": m.group(2)})
    if not file_entries:
        for m in re.finditer(r"\{[^{}]*?\"file\"\s*:\s*\{[\s\S]*?\"fid\":\s*\"?(\d+)\"?[\s\S]*?\"name\":\s*\"([^\"]+)\"", html):
            file_entries.append({"fid": m.group(1), "name": m.group(2)})
    info["files"] = file_entries
    return info

def try_get_download_url(share_id: str, fid: str, cookie: str) -> str:
    if not cookie:
        return ""
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Origin": "https://pan.quark.cn",
        "Referer": "https://pan.quark.cn/",
    }
    endpoints = [
        "https://drive.quark.cn/1/clouddrive/sharefile/download",
        "https://drive.quark.cn/1/clouddrive/file/download",
    ]
    payloads = [
        {"share_id": share_id, "fid": fid},
        {"fid": fid},
    ]
    for url, data in zip(endpoints, payloads):
        try:
            r = requests.post(url, headers=headers, json=data, timeout=15)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict):
                    dl = j.get("download_url") or j.get("data", {}).get("download_url")
                    if dl:
                        return dl
        except Exception:
            continue
    return ""

st.title("夸克直链解析")
pwd = st.text_input("访问密码", type="password", placeholder="请输入访问密码")
if pwd == "888888":
    cookie = st.text_area("夸克 Cookie", placeholder="粘贴你的夸克 Cookie 字符串")
    link = st.text_input("分享链接", placeholder="https://pan.quark.cn/s/xxxx 或 https://pan.quark.cn/s/xxxx?pwd=123456")
    go = st.button("开始解析")
    if go:
        if not link:
            st.error("请填写分享链接")
        else:
            m = share_pattern.match(link.strip())
            if not m:
                st.error("链接格式无效，需形如 https://pan.quark.cn/s/xxxx 或附带 ?pwd=提取码")
            else:
                share_code = m.group(1)
                pwd_code = m.group(2) or ""
                normalized = f"https://pan.quark.cn/s/{share_code}"
                if pwd_code:
                    normalized += f"?pwd={pwd_code}"
                with st.spinner("解析中..."):
                    try:
                        html = fetch_share_page(normalized)
                        info = extract_share_info(html)
                        title = info.get("title") or "分享页"
                        st.subheader(title)
                        files = info.get("files") or []
                        share_id = info.get("share_id") or ""
                        if not files:
                            st.info("未提取到文件列表，可能需要登录或链接内容为空。")
                        else:
                            for f in files:
                                name = f.get("name") or "(未知文件)"
                                fid = f.get("fid")
                                direct = try_get_download_url(share_id, fid, cookie)
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.write(name)
                                with col2:
                                    if direct:
                                        st.link_button("点击下载", direct, use_container_width=True)
                                        st.code(direct, language="text")
                                    else:
                                        st.warning("直链未获取，检查Cookie或稍后重试")
                        if not cookie:
                            st.caption("提示：夸克直链下载通常需要携带登录 Cookie。未设置时可能无法获取直链。")
                    except Exception as e:
                        st.error(f"解析失败：{str(e)}")
else:
    st.info("请输入访问密码以显示解析功能。")