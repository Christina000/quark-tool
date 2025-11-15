import streamlit as st
import requests
import re

st.set_page_config(page_title="夸克直链解析（调试版）", layout="centered")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
DIR_URL = "https://drive.quark.cn/1/clouddrive/share/share_page/dir"
DL_URL_SHARE = "https://drive.quark.cn/1/clouddrive/sharefile/download"
DL_URL_FILE = "https://drive.quark.cn/1/clouddrive/file/download"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://pan.quark.cn",
    "Referer": "https://pan.quark.cn/",
    "User-Agent": UA,
}
PARAMS = {"pr": "ucpro", "fr": "pc"}
LINK_RE = re.compile(r"^https?://pan\.quark\.cn/s/([A-Za-z0-9]+)(?:\?pwd=([A-Za-z0-9]+))?$")

def human_size(n):
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

def parse_link(link):
    m = LINK_RE.match(link.strip())
    if not m:
        return None, None
    return m.group(1), (m.group(2) or "")

def request_dir(cookie, pwd_id, passcode=""):
    headers = dict(HEADERS)
    headers["Cookie"] = cookie.strip()
    body = {"pwd_id": pwd_id, "dir_fid": "0", "pdir_fid": "0", "force": 0}
    if passcode:
        body["code"] = passcode
    r = requests.post(DIR_URL, headers=headers, params=PARAMS, json=body, timeout=20)
    return r, body, headers

def get_download_url(cookie, share_id, fid):
    headers = dict(HEADERS)
    headers["Cookie"] = cookie.strip()
    body1 = {"share_id": share_id, "fid": fid, "sign_type": 2}
    r1 = requests.post(DL_URL_SHARE, headers=headers, params=PARAMS, json=body1, timeout=20)
    try:
        j1 = r1.json()
    except Exception:
        j1 = None
    if r1.status_code == 200 and isinstance(j1, dict):
        u = j1.get("download_url") or (j1.get("data") or {}).get("download_url")
        if u:
            return u, ("sharefile/download", r1, body1, headers)
    body2 = {"fid": fid}
    r2 = requests.post(DL_URL_FILE, headers=headers, params=PARAMS, json=body2, timeout=20)
    try:
        j2 = r2.json()
    except Exception:
        j2 = None
    if r2.status_code == 200 and isinstance(j2, dict):
        u2 = j2.get("download_url") or (j2.get("data") or {}).get("download_url")
        if u2:
            return u2, ("file/download", r2, body2, headers)
    return "", ("sharefile/download", r1, body1, headers)

st.title("夸克直链解析（调试版）")
gate = st.text_input("访问密码", type="password", placeholder="请输入访问密码")
if gate != "888888":
    st.info("请输入访问密码以显示解析功能。")
    st.stop()

cookie = st.text_area("夸克 Cookie", placeholder="粘贴你的夸克 Cookie 字符串")
link = st.text_input("分享链接", placeholder="https://pan.quark.cn/s/xxxx 或 https://pan.quark.cn/s/xxxx?pwd=123456")
start = st.button("开始解析")

if "dl_dbg" not in st.session_state:
    st.session_state["dl_dbg"] = {}

if start:
    if not cookie:
        st.error("请粘贴 Cookie")
        st.stop()
    if not link:
        st.error("请填写分享链接")
        st.stop()
    pwd_id, passcode = parse_link(link)
    if not pwd_id:
        st.error("链接格式无效，需形如 https://pan.quark.cn/s/xxxx 或附带 ?pwd=提取码")
        st.stop()

    with st.spinner("请求文件列表中..."):
        try:
            resp, body, used_headers = request_dir(cookie, pwd_id, passcode or "")
            st.write("请求URL:", DIR_URL)
            st.write("请求查询参数:", PARAMS)
            st.write("请求头:", used_headers)
            st.write("请求体:", body)
            st.write("响应状态码:", resp.status_code)
            ct = resp.headers.get("Content-Type", "")
            st.write("响应Content-Type:", ct)
            data_json = None
            try:
                data_json = resp.json()
                st.json(data_json)
            except Exception:
                st.write(resp.text)

            if resp.status_code != 200:
                st.error("请求失败，请检查上方响应详情。")
                st.stop()

            if not isinstance(data_json, dict):
                st.error("响应非JSON或结构异常，请查看上方原始响应。")
                st.stop()

            if data_json.get("code") == 40005:
                st.error("API 需要验证，目前代码可能不支持带密码的私密分享，请尝试公开分享链接")
                st.stop()

            d = data_json.get("data") or {}
            items = d.get("list") or d.get("items") or []
            share_id = d.get("share_id") or pwd_id

            if not items:
                st.error("未获取到文件列表。请查看上方JSON了解具体错误信息。")
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
                        k = f"get_{fid}"
                        if st.button("获取直链", key=k):
                            url, dbg = get_download_url(cookie, share_id, fid)
                            st.session_state["dl_dbg"][fid] = (url, dbg)
                        if fid in st.session_state["dl_dbg"]:
                            u, dbg = st.session_state["dl_dbg"][fid]
                            api_name, r, req_body, req_headers = dbg
                            st.write("直链接口:", api_name)
                            st.write("直链请求体:", req_body)
                            st.write("直链请求头:", req_headers)
                            st.write("直链响应状态码:", r.status_code)
                            try:
                                st.json(r.json())
                            except Exception:
                                st.write(r.text)
                            if u:
                                st.link_button("点击下载", u, use_container_width=True)
                                st.code(u, language="text")
                            else:
                                st.warning("直链未获取，查看上方响应详情排查原因")

            st.caption("提示：直链下载通常需要浏览器携带登录 Cookie；Referer 必须为 https://pan.quark.cn。")

        except Exception as e:
            st.error(f"解析失败：{str(e)}")