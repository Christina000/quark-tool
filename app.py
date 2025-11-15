import streamlit as st
import requests
import re
import json
from typing import Dict, Any, List, Tuple, Optional

st.set_page_config(page_title="夸克直链解析（API版）", layout="centered")

# 基本常量
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
BASE = "https://drive.quark.cn/1/clouddrive"
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://pan.quark.cn",
    "Referer": "https://pan.quark.cn/",
    "User-Agent": UA,
}
SHARE_LINK_RE = re.compile(r"^https?://pan\.quark\.cn/s/([A-Za-z0-9]+)(?:\?pwd=([A-Za-z0-9]+))?$")

# 工具
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

def api_request(path: str, method: str, cookie: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    url = f"{BASE}{path}"
    headers = dict(DEFAULT_HEADERS)
    headers["Cookie"] = (cookie or "").strip()
    q = {"pr": "ucpro", "fr": "pc"}
    if params:
        q.update(params)
    if method.upper() == "GET":
        r = requests.get(url, headers=headers, params=q, timeout=15)
    else:
        headers["Content-Type"] = "application/json"
        r = requests.post(url, headers=headers, params=q, json=data or {}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        return r.json()
    except Exception:
        raise RuntimeError("响应非JSON")

def fetch_html(link: str, cookie: str = "") -> str:
    headers = dict(DEFAULT_HEADERS)
    if cookie:
        headers["Cookie"] = cookie.strip()
    r = requests.get(link, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"访问分享页失败: HTTP {r.status_code}")
    return r.text

def extract_params_from_html(html: str) -> Dict[str, Any]:
    # 尝试在 window.__INITIAL_STATE__ 或 window.g_config 中提取关键参数
    # 为提高健壮性，不强制反序列化整段 JSON，而是逐项正则匹配
    params = {"stoken": None, "pdir_fid": "0", "share_id": None, "title": None}
    # 标题（可选）
    m_title = re.search(r"<title>(.*?)</title>", html, flags=re.S | re.I)
    if m_title:
        params["title"] = re.sub(r"\s+", " ", m_title.group(1)).strip()

    # 直接匹配关键键值
    keys = {
        "stoken": r"[\"']stoken[\"']\s*:\s*[\"']([^\"']+)[\"']",
        "share_id": r"[\"']share[_ ]?id[\"']\s*:\s*[\"']?([0-9]+)[\"']?",
        "pdir_fid": r"[\"']pdir[_ ]?fid[\"']\s*:\s*[\"']?([0-9]+)[\"']?",
    }
    for k, pat in keys.items():
        m = re.search(pat, html, flags=re.I)
        if m:
            params[k] = m.group(1)

    # 兼容 g_config/INITIAL_STATE 中的路径信息（有些页面把根目录 id 放在 listPath 或 rootId）
    m_root = re.search(r"[\"']root[_ ]?id[\"']\s*:\s*[\"']?([0-9]+)[\"']?", html, flags=re.I)
    if m_root and not params.get("pdir_fid"):
        params["pdir_fid"] = m_root.group(1)

    return params

def normalize_link(link: str) -> Tuple[Optional[str], Optional[str]]:
    m = SHARE_LINK_RE.match(link.strip())
    if not m:
        return None, None
    return m.group(1), (m.group(2) or "")

def get_share_info_via_api(link: str, cookie: str, passcode: str) -> Dict[str, Any]:
    # 作为 HTML 解析失败的兜底：通过分享信息接口拿到 pwd_id/passcode/stoken
    payload = {"text": link}
    for p in ["/share/info", "/share/get", "/share_info"]:
        try:
            j = api_request(p, "POST", cookie, data=payload)
            if j.get("code") == 0 and j.get("data"):
                data = j["data"]
                info = {
                    "pwd_id": data.get("pwd_id"),
                    "passcode": passcode or data.get("passcode") or "",
                    "share_id": data.get("share_id"),
                    "stoken": data.get("stoken"),
                }
                return info
        except Exception:
            continue
    return {"pwd_id": None, "passcode": passcode, "share_id": None, "stoken": None}

def get_stoken_via_api(pwd_id: str, passcode: str, cookie: str) -> Optional[str]:
    if not pwd_id:
        return None
    payload = {"pwd_id": pwd_id, "passcode": passcode or ""}
    for p in ["/share/stoken", "/share/token", "/share/access"]:
        try:
            j = api_request(p, "POST", cookie, data=payload)
            if j.get("code") == 0 and j.get("data"):
                stoken = j["data"].get("stoken")
                if stoken:
                    return stoken
        except Exception:
            continue
    return None

def list_dir_via_api(stoken: str, pdir_fid: str, cookie: str, page: int = 1, size: int = 200) -> Dict[str, Any]:
    # 优先使用 share_page/dir；失败则尝试设置排序后再拉取
    payload = {"stoken": stoken, "pdir_fid": str(pdir_fid), "page": page, "size": size}
    try:
        j = api_request("/share/share_page/dir", "POST", cookie, data=payload)
        if j.get("code") == 0 and j.get("data"):
            return j["data"]
    except Exception:
        pass
    try:
        sort_payload = {"stoken": stoken, "sort": "file_name", "order": "asc"}
        api_request("/share/share_page/sort", "POST", cookie, data=sort_payload)
        j2 = api_request("/share/share_page/dir", "POST", cookie, data=payload)
        if j2.get("code") == 0 and j2.get("data"):
            return j2["data"]
    except Exception:
        pass
    # 再兜底调用旧列表接口
    try:
        j3 = api_request("/share/list", "POST", cookie, data={"pwd_id": "", "stoken": stoken, "pdir_fid": str(pdir_fid), "page": page, "size": size})
        if j3.get("code") == 0 and j3.get("data"):
            # 统一结构
            d = j3["data"]
            return {"list": d.get("list") or d.get("items") or [], "share_id": d.get("share_id") or ""}
    except Exception:
        pass
    return {"list": [], "share_id": ""}

def get_download_url(share_id: str, fid: str, cookie: str) -> str:
    # 先试 sharefile/download，再试 file/download
    try:
        j = api_request("/sharefile/download", "POST", cookie, data={"share_id": share_id, "fid": fid})
        url = j.get("download_url") or (j.get("data") or {}).get("download_url")
        if url:
            return url
    except Exception:
        pass
    try:
        j2 = api_request("/file/download", "POST", cookie, data={"fid": fid})
        url2 = j2.get("download_url") or (j2.get("data") or {}).get("download_url")
        if url2:
            return url2
    except Exception:
        pass
    return ""

# 界面
st.title("夸克直链解析（API版）")
gate = st.text_input("访问密码", type="password", placeholder="请输入访问密码")
if gate != "888888":
    st.info("请输入访问密码以显示解析功能。")
    st.stop()

cookie = st.text_area("夸克 Cookie", placeholder="粘贴你的夸克 Cookie 字符串")
link = st.text_input("分享链接", placeholder="https://pan.quark.cn/s/xxxx 或 https://pan.quark.cn/s/xxxx?pwd=123456")
start = st.button("开始解析")

if start:
    if not cookie:
        st.error("请粘贴 Cookie")
        st.stop()
    if not link:
        st.error("请填写分享链接")
        st.stop()
    code, passcode = SHARE_LINK_RE.match(link.strip()).groups() if SHARE_LINK_RE.match(link.strip()) else (None, None)
    if not code:
        st.error("链接格式无效，需形如 https://pan.quark.cn/s/xxxx 或附带 ?pwd=提取码")
        st.stop()

    with st.spinner("解析中..."):
        try:
            # 第一步：抓取 HTML，提取 stoken / pdir_fid / share_id
            html = fetch_html(link, cookie)
            params = extract_params_from_html(html)
            stoken = params.get("stoken")
            pdir_fid = params.get("pdir_fid") or "0"
            share_id = params.get("share_id") or ""

            # 兜底：如果未能从HTML提取到 stoken，则走分享信息 + stoken接口
            if not stoken:
                info = get_share_info_via_api(link, cookie, passcode or "")
                stoken = info.get("stoken") or get_stoken_via_api(info.get("pwd_id"), info.get("passcode") or (passcode or ""), cookie)
                share_id = share_id or info.get("share_id") or ""

            if not stoken:
                st.error("未获取到 stoken，Cookie 可能失效或链接异常。")
                st.stop()

            # 第二步：调用 API 拉取文件列表（根目录）
            data = list_dir_via_api(stoken, pdir_fid, cookie)
            items = data.get("list") or []
            share_id = share_id or data.get("share_id") or ""

            if not items:
                st.error("未获取到文件列表。可能是私密分享或Cookie失效。")
                st.stop()

            # 第三步：展示文件名、大小，并提供【获取直链】按钮
            st.subheader(params.get("title") or "分享文件列表")
            for it in items:
                # 兼容不同字段命名
                name = it.get("file_name") or it.get("name") or "(未知文件)"
                fid = it.get("fid") or it.get("file_id") or ""
                size = it.get("size") or it.get("file_size") or 0
                is_dir = False
                t = (it.get("type") or it.get("file_type") or "").lower()
                # 多种可能的目录判断
                if t in ("folder", "dir"):
                    is_dir = True
                if it.get("is_dir") in (True, "true", "1"):
                    is_dir = True

                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    st.write(name)
                with c2:
                    st.write(human_size(size))
                with c3:
                    if is_dir:
                        st.caption("暂不支持递归进入子文件夹")
                    else:
                        btn_key = f"dl_{fid}"
                        if st.button("获取直链", key=btn_key):
                            url = get_download_url(share_id, fid, cookie)
                            if url:
                                st.link_button("点击下载", url, use_container_width=True)
                                st.code(url, language="text")
                            else:
                                st.warning("直链未获取，检查Cookie或稍后重试")

            st.caption("提示：直链下载通常需要浏览器携带登录 Cookie；Referer 必须为 https://pan.quark.cn。")

        except Exception as e:
            st.error(f"解析失败：{str(e)}")