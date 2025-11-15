import streamlit as st
import requests
import re
import json

st.set_page_config(page_title="夸克直链解析 (API V2修复版)", layout="centered")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_files_from_api(share_url, cookie, pwd_code=""):
    # 1. 提取分享ID
    try:
        match = re.search(r"s/([a-zA-Z0-9]+)", share_url)
        if not match:
            return False, "链接格式错误，未找到分享ID"
        pwd_id = match.group(1)
    except Exception as e:
        return False, str(e)

    # 2. 定义可能的接口列表 (这是关键修改点！)
    # 移除了 share_page/sort 这种老接口，换成了 share_file_list
    endpoints = [
        # 接口 A: 通用分享列表
        "https://pan.quark.cn/1/clouddrive/share/share_file_list?pr=ucpro&fr=pc",
        # 接口 B: 备用驱动域名
        "https://drive.quark.cn/1/clouddrive/share/share_file_list?pr=ucpro&fr=pc",
        # 接口 C: V2版本接口 (通常更稳)
        "https://pan.quark.cn/1/clouddrive/share/share_data?pr=ucpro&fr=pc"
    ]
    
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Referer": "https://pan.quark.cn/", 
        "Origin": "https://pan.quark.cn",
        "Accept": "application/json, text/plain, */*"
    }

    # 3. 准备参数 (注意：新接口参数略有不同)
    # stoken 需要置空，让 Cookie 自动处理
    payload = {
        "pwd_id": pwd_id,
        "dir_fid": "0",
        "pdir_fid": "0",
        "force": 0,
        "stoken": "",
        "pdir_key": "",
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
                
                # 成功情况
                if code == 0:
                    # 提取数据的兼容逻辑
                    # 有时候在 data.list，有时候在 data.share_file_list
                    data_body = data.get("data", {})
                    
                    if "list" in data_body:
                        return True, data_body["list"]
                    elif "share_file_list" in data_body:
                        return True, data_body["share_file_list"]
                    elif isinstance(data_body, list):
                         return True, data_body
                    else:
                        # 空文件夹
                        return True, []
                        
                elif code == 40005:
                    return False, "需要提取码验证，或密码错误。"
                else:
                    msg = data.get("message", "未知业务错误")
                    error_log.append(f"{api_url} -> {msg}")
            else:
                error_log.append(f"{api_url} -> HTTP {r.status_code}")
        except Exception as e:
            error_log.append(f"{api_url} -> 异常: {str(e)}")
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
st.title("夸克直链解析 (V2接口版)")
pwd = st.text_input("访问密码", type="password")

if pwd == "888888":
    st.caption("提示：若一直失败，请尝试在浏览器隐私模式下重新获取 Cookie")
    cookie_input = st.text_area("夸克 Cookie", height=100)
    link_input = st.text_input("分享链接")
    
    if st.button("开始解析"):
        if not cookie_input or not link_input:
            st.error("请填写完整信息")
        else:
            # 简单的pwd提取
            pwd_code = ""
            if "pwd=" in link_input:
                try:
                    pwd_code = link_input.split("pwd=")[1].split("&")[0]
                except: pass

            with st.spinner("正在尝试 V2 接口..."):
                success, result = get_files_from_api(link_input, cookie_input, pwd_code)
                
                if success:
                    st.success("🎉 成功获取文件！")
                    # 提取share_id
                    try:
                        share_id = re.search(r"s/([a-zA-Z0-9]+)", link_input).group(1)
                    except:
                        share_id = ""
                    
                    if not result:
                        st.warning("文件夹为空。")
                    
                    for f in result:
                        col1, col2 = st.columns([3, 1])
                        # 兼容不同字段名
                        fname = f.get('file_name') or f.get('name') or '未知文件'
                        fid = f.get('fid')
                        is_dir = f.get('obj_category') == 'dir' or f.get('type') == 1
                        
                        with col1:
                            st.write(f"📄 {fname}")
                        with col2:
                            if not is_dir:
                                dl = get_download_link(share_id, fid, cookie_input)
                                if dl:
                                    st.link_button("下载", dl)
                                else:
                                    st.caption("失败")
                            else:
                                st.caption("文件夹")
                else:
                    st.error("所有接口均尝试失败，日志：")
                    st.code(result)
else:
    st.info("请输入访问密码")
