import streamlit as st
import requests
import re
from typing import Dict, Any, List, Optional, Tuple

st.set_page_config(page_title="夸克直链解析（API版）", layout="centered")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
BASES = [
    "https://pan.quark.cn/1/clouddrive",
    "https://drive.quark.cn/1/clouddrive",
]
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://pan.quark.cn",
    "Referer": "https://pan.quark.cn/",
    "User-Agent": UA,
}
LINK_RE = re.compile(r"^https?://pan\.quark\.cn/s/([A-Za-z0-9]+)(?:\?pwd=([A-Za-z0-9]+))?$")

def parse_link(link: str) -> Tuple[Optional[str], Optional[str]]:
    m = LINK_RE.match(link.strip())
    if not m:
        return None, None
    return m.group(1), (m.group(2) or "")

def post_json(path: str, cookie: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = dict(HEADERS)
    headers["Cookie"] = cookie.strip()
    params = {"pr": "ucpro", "fr": "pc"}
    last_err = None
    for base in BASES:
        try:
            url = f"{base}{path}"
            r = requests.post(url, headers=headers, params=params, json=body, timeout=15)
            if r.status_code != 200:
                last_err = RuntimeError(f"HTTP {r.status_code}")
                continue
            return r.json()
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return {}

def list_files(cookie: str, share_code: str, passcode: str, page: int = 1, size: int = 50) -> Dict[str, Any]:
    bodies = [
        {"pwd_id": share_code, "dir_fid": "0", "pdir_fid": "0", "force": 0, "_page": page, "_size": size},
        {"pwd_id": share_code, "pdir_fid": "0", "page": page, "size": size},
        {"pwd_id": share_code, "dir_fid": "0", "pdir_fid": "0", "page": page, "size": size},
        {"pwd_id": share_code, "pdir_fid": "0", "_page": page, "_size": size},
    ]
    if passcode:
        for b in bodies:
            b.update({"code": passcode})
    paths = [
        "/share/share_page/sort",
        "/share/share_page/dir",
        "/share/list",
    ]
    for path in paths:
        for body in bodies:
            try:
                j = post_json(path, cookie, body)
                if isinstance(j, dict):
                    code = j.get("code")
                    if code == 0 and j.get("data"):
                        return j["data"]
                    if code == 40005:
                        raise RuntimeError("API 需要验证，目前代码可能不支持带密码的私密分享，请尝试公开分享链接")
            except RuntimeError as e:
                if "需要验证" in str(e):
                    raise
                continue
            except Exception:
                continue
    return {"list": [], "share_id": ""}

def get_download_url(cookie: str, share_id: str, fid: str) -> str:
    body1 = {"share_id": share_id, "fid": fid, "sign_type": 2}
    try:
        j = post_json("/sharefile/download", cookie, body1)
        url = j.get("download_url") or (j.get("data") or {}).get("download_url")
        if url:
            return url
    except Exception:
        pass
    try:
        j2 = post_json("/file/download", cookie, {"fid": fid})
        url2 = j2.get("download_url") or (j2.get("data") or {}).get("download_url")
        if url2:
            return url2
    except Exception:
        pass
    return ""

def human_size(n: Optional[int]) -> str:
    try:
        n = int(n or 0)
    except Exception:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f"{n:.2f} {units[i]}"

st.title("夸克直链解析（API版）")
gate = st.text_input("访问密码", type="password", placeholder="请输入访问密码")
if gate != "888888":
    st.info("请输入访问密码以显示解析功能。")
    st.stop()

cookie = st.text_area("夸克 Cookie", placeholder="粘贴你的夸克 Cookie 字符串")
link = st.text_input("分享链接", placeholder="https://pan.quark.cn/s/xxxx 或 https://pan.quark.cn/s/xxxx?pwd=123456")
start = st.button("开始解析")

if "dl_cache" not in st.session_state:
    st.session_state["dl_cache"] = {}

if start:
    if not cookie:
        st.error("请粘贴 Cookie")
        st.stop()
    if not link:
        st.error("请填写分享链接")
        st.stop()
    share_code, passcode = parse_link(link)
    if not share_code:
        st.error("链接格式无效，需形如 https://pan.quark.cn/s/xxxx 或附带 ?pwd=提取码")
        st.stop()
    with st.spinner("解析中..."):
        try:
            data = list_files(cookie, share_code, passcode or "")
            items = data.get("list") or data.get("items") or []
            share_id = data.get("share_id") or share_code
            if not items:
                st.error("未获取到文件列表。可能是私密分享或Cookie失效。")
                st.stop()
            st.subheader("文件列表")
            for it in items:
                name = it.get("file_name") or it.get("name") or "(未知文件)"
                fid = it.get("fid") or it.get("file_id") or ""
                size = it.get("size") or it.get("file_size") or 0
                t = (it.get("type") or it.get("file_type") or "").lower()
                is_dir = it.get("is_dir") in (True, "true", "1") or t in ("folder", "dir")
                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    st.write(name)
                with c2:
                    st.write(human_size(size))
                with c3:
                    if is_dir:
                        st.caption("暂不支持递归进入子文件夹")
                    else:
                        k = f"btn_{fid}"
                        if st.button("获取直链", key=k):
                            url = get_download_url(cookie, share_id, fid)
                            if url:
                                st.session_state["dl_cache"][fid] = url
                            else:
                                st.session_state["dl_cache"][fid] = ""
                        if fid in st.session_state["dl_cache"]:
                            u = st.session_state["dl_cache"][fid]
                            if u:
                                st.link_button("点击下载", u, use_container_width=True)
                                st.code(u, language="text")
                            else:
                                st.warning("直链未获取，检查Cookie或稍后重试")
            st.caption("提示：直链下载通常需要浏览器携带登录 Cookie；Referer 必须为 https://pan.quark.cn。")
        except RuntimeError as e:
            if "需要验证" in str(e):
                st.error("API 需要验证，目前代码可能不支持带密码的私密分享，请尝试公开分享链接")
            else:
                st.error(f"解析失败：{str(e)}")
        except Exception as e:
            st.error(f"解析失败：{str(e)}")