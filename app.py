import streamlit as st
import requests
import re
import json

st.set_page_config(page_title="夸克直链解析", layout="centered")

# 模拟浏览器头部
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_files_from_api(share_url, cookie, pwd_code=""):
    # 1. 提取分享ID (s/后面那串)
    try:
        match = re.search(r"s/([a-zA-Z0-9]+)", share_url)
        if not match:
            return False, "链接格式错误，未找到分享ID"
        pwd_id = match.group(1)
    except Exception as e:
        return False, str(e)

    # 2. 定义可能的接口列表
    # 包含 pan 和 drive 两个域名，sort 和 list 两个接口
    endpoints = [
        "https://drive.quark.cn/1/clouddrive/share/share_page/list?pr=ucpro&fr=pc",
        "https://drive.quark.cn/1/clouddrive/share/share_page/sort?pr=ucpro&fr=pc",
        "https://pan.quark.cn/1/clouddrive/share/share_page/list?pr=ucpro&fr=pc",
        "https://pan.quark.cn/1/clouddrive/share/share_page/sort?pr=ucpro&fr=pc"
    ]
    
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Referer": "https://pan.quark.cn/", 
        "Origin": "https://pan.quark.cn",
        "Accept": "application/json, text/plain, */*"
    }

    # 3. 准备参数
    payload = {
        "pwd_id": pwd_id,
        "dir_fid": "0",
        "pdir_fid": "0",
        "force": 0,
        "sort_type": 6,
        "_page": 1,
        "_size": 50
    }
    if pwd_code:
        payload["passcode"] = pwd_code

    # 4. 轮询尝试
    error_log = []
    for api_url in endpoints:
        try:
            r = requests.post(api_url, headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                code = data.get("code")
                if code == 0:
                    # 成功！兼容不同结构
                    data_body = data.get("data", {})
                    # 有些接口直接返回 list，有些在 data 下
                    if isinstance(data_body, list):
                        return True, data_body
                    else:
                        flist = data_body.get("list")
                        if flist is not None:
                            return True, flist
                        # 如果data是字典但没有list，可能直接就是list
                        if "list" in data:
                            return True, data["list"]
                        # 空文件夹情况
                        return True, []
                elif code == 40005:
                    return False, "需要提取码，但验证失败。"
                else:
                    msg = data.get("message", "未知错误")
                    error_log.append(f"{api_url} -> {msg}")
            else:
                error_log.append(f"{api_url} -> HTTP {r.status_code}")
        except Exception as e:
            error_log.append(f"{api_url} -> {str(e)}")
            continue
    
    return False, "\n".join(error_log)

def get_download_link(share_id, fid, cookie):
    url = "https://drive.quark.cn/1/clouddrive/sharefile/download"
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Referer": "https://pan.quark.cn/"
    }
    data = {"share_id": share_id, "fid": fid, "sign_type": 2}
    try:
        r = requests.post(url, headers=headers, json=data, timeout=8)
        if r.status_code == 200:
            return r.json().get("data", {}).get("download_url")
    except:
        pass
    return None

# --- 界面逻辑 ---
st.title("夸克直链解析")
pwd = st.text_input("访问密码", type="password")

if pwd == "888888":
    st.caption("提示：请确保Cookie完整且有效（推荐使用无痕模式获取）")
    cookie_input = st.text_area("夸克 Cookie", height=100)
    link_input = st.text_input("分享链接")
    
    if st.button("开始解析"):
        if not cookie_input or not link_input:
            st.error("请填写完整信息")
        else:
            # 提取链接里的pwd参数
            pwd_code = ""
            # 这里是你之前报错的地方，已简化写法
            if "pwd=" in link_input:
                try:
                    split_url = link_input.split("pwd=")
                    if len(split_url) > 1:
                        pwd_code = split_url[1].split("&")[0]
                except:
                    pass

            with st.spinner("正在尝试连接夸克服务器..."):
                success, result = get_files_from_api(link_input, cookie_input, pwd_code)
                
                if success:
                    st.success("🎉 成功获取文件！")
                    # 提取share_id
                    sid_match = re.search(r"s/([a-zA-Z0-9]+)", link_input)
                    share_id = sid_match.group(1) if sid_match else ""
                    
                    if not result:
                        st.warning("文件夹为空或未解析到内容。")
                    
                    for f in result:
                        col1, col2 = st.columns([3, 1])
                        fname = f.get('file_name', '未知文件')
                        with col1:
                            st.write(f"📄 {fname}")
                        with col2:
                            # 只有文件才显示下载
                            if f.get('obj_category') != 'dir':
                                dl = get_download_link(share_id, f['fid'], cookie_input)
                                if dl:
                                    st.link_button("下载", dl)
                                else:
                                    st.caption("失败")
                            else:
                                st.caption("文件夹")
                else:
                    st.error("解析失败，调试日志：")
                    st.code(result)
else:
    st.info("请输入访问密码")
