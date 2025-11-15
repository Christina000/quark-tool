import streamlit as st
import requests
import re
import json

st.set_page_config(page_title="夸克直链解析 (全域名轰炸版)", layout="centered")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_files_from_api(share_url, cookie, pwd_code=""):
    # 1. 提取 pwd_id
    try:
        match = re.search(r"s/([a-zA-Z0-9]+)", share_url)
        if not match:
            return False, "链接格式错误，未找到分享ID"
        pwd_id = match.group(1)
    except Exception as e:
        return False, f"链接解析错误: {str(e)}"

    # 2. 定义可能的接口列表 (包含 pan 和 drive 两个域名)
    # 很多时候 API 其实在 drive.quark.cn 上
    possible_endpoints = [
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
    for api_url in possible_endpoints:
        try:
            # st.write(f"尝试: {api_url}") # 调试显示
            r = requests.post(api_url, headers=headers, json=payload, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                # 只要 code=0 且数据里有 list，就是成功
                if data.get("code") == 0:
                    file_list = data.get("data", {}).get("list") or data.get("list")
                    if file_list:
                        return True, file_list
                    else:
                         # 有时候是空文件夹
                         return True, []
                elif data.get("code") == 40005:
                    return False, "需要提取码验证，但接口拒绝了当前密码。"
                else:
                    error_log.append(f"❌ {api_url} 业务报错: {data.get('message')}")
            else:
                error_log.append(f"❌ {api_url} HTTP状态: {r.status_code}")
        except Exception as e:
            error_log.append(f"❌ {api_url} 异常: {str(e)}")
            continue
    
    # 如果循环结束都没返回 True，打印所有尝试的错误
    return False, "\n".join(error_log)

def get_download_link(share_id, fid, cookie):
    # 下载接口通常也都在 drive 域名下
    url = "https://drive.quark.cn/1/clouddrive/sharefile/download"
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Referer": "https://pan.quark.cn/"
    }
    data = {"share_id": share_id, "fid": fid, "sign_type": 2}
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            return r.json().get("data", {}).get("download_url")
    except:
        pass
    return None

st.title("夸克直链解析 (全域名轰炸版)")
pwd = st.text_input("访问密码", type="password")

if pwd == "888888":
    st.caption("如果解析失败，请尝试重新获取最新的 Cookie")
    cookie_input = st.text_area("夸克 Cookie", height=100)
    link_input = st.text_input("分享链接")
    
    if st.button("开始解析"):
        if not cookie_input or not link_input:
            st.error("请填写完整信息")
        else:
            pwd_code = ""
            match = re.search(r"pwd=([a-zA-Z0-9]+)", link_input)
            if match: pwd_code = match.group(1)

            with st.spinner("正在尝试 pan.quark.cn 和 drive.quark.cn 所有接口..."):
                success, result = get_files_from_api(link_input, cookie_input, pwd_code)
                
                if success:
                    st.success("🎉 成功获取文件！")
                    match_id = re.search(r"s/([a-zA-Z0-9]+)", link_input)
                    share_id = match_id.group(1) if match_id else ""
                    
                    if not result:
                        st.warning("文件夹是空的，或者没有解析到文件。")
                    
                    for f in result:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📄 {f