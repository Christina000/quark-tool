import streamlit as st
import requests
import re
import json

st.set_page_config(page_title="夸克直链解析 (最终决战版)", layout="centered")

# 模拟浏览器指纹
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_files_from_api(share_url, cookie, pwd_code=""):
    # 1. 提取 pwd_id
    try:
        match = re.search(r"s/([a-zA-Z0-9]+)", share_url)
        if not match:
            return False, "链接格式错误，未找到分享ID"
        pwd_id = match.group(1)
    except Exception as e:
        return False, str(e)

    # 2. 接口列表 (地毯式搜索)
    # 注意：夸克的 API 大多在 drive.quark.cn，而不是 pan.quark.cn
    endpoints = [
        # 可能性 1: 文件夹专用排序接口 (最常用)
        "https://drive.quark.cn/1/clouddrive/share/share_sort?pr=ucpro&fr=pc",
        # 可能性 2: 通用文件列表接口
        "https://drive.quark.cn/1/clouddrive/share/share_file_list?pr=ucpro&fr=pc",
        # 可能性 3: 旧版接口
        "https://pan.quark.cn/1/clouddrive/share/share_page/sort?pr=ucpro&fr=pc",
        # 可能性 4: 备用接口
        "https://drive.quark.cn/1/clouddrive/share/detail?pr=ucpro&fr=pc"
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
        "sort_type": 6, # 6=按时间排序
        "_page": 1,
        "_size": 50
    }
    if pwd_code:
        payload["passcode"] = pwd_code

    # 4. 开始轮询
    error_log = []
    for api_url in endpoints:
        try:
            r = requests.post(api_url, headers=headers, json=payload, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                code = data.get("code")
                
                if code == 0:
                    # 成功！尝试提取 list 数据
                    data_body = data.get("data", {})
                    
                    # 夸克不同接口返回的字段名不一样，这里做兼容
                    final_list = None
                    if "list" in data_body: final_list = data_body["list"]
                    elif "share_file_list" in data_body: final_list = data_body["share_file_list"]
                    elif isinstance(data_body, list): final_list = data_body
                    
                    if final_list is not None:
                        return True, final_list
                    else:
                        # 可能是空文件夹，也算成功
                        return True, []
                        
                elif code == 40005:
                    return False, "需要输入提取码，或者提取码错误。"
                else:
                    error_log.append(f"❌ {api_url} 业务错误: {data.get('message')}")
            else:
                error_log.append(f"❌ {api_url} HTTP状态: {r.status_code}")
        except Exception as e:
            error_log.append(f"⚠️ {api_url} 异常: {str(e)}")
            continue
    
    return False, "所有接口尝试均失败。\n" + "\n".join(error_log)

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

# --- 界面 ---
st.title("夸克直链解析 (决战版)")
pwd = st.text_input("访问密码", type="password")

if pwd == "888888":
    st.success("Cookie 状态：已准备就绪")
    cookie_input = st.text_area("请粘贴刚才找到的 Cookie (以 __puus 开头)", height=100)
    link_input = st.text_input("分享链接")
    
    if st.button("开始解析"):
        if not cookie_input or not link_input:
            st.error("请填写完整信息")
        else:
            # 自动提取提取码
            pwd_code = ""
            if "pwd=" in link_input:
                try: pwd_code = link_input.split("pwd=")[1].split("&")[0]
                except: pass

            with st.spinner("正在地毯式搜索有效接口..."):
                success, result = get_files_from_api(link_input, cookie_input, pwd_code)
                
                if success:
                    st.balloons() # 成功时放个气球庆祝一下！
                    st.success("🎉 终于成功了！")
                    
                    # 提取share_id
                    try: share_id = re.search(r"s/([a-zA-Z0-9]+)", link_input).group(1)
                    except: share_id = ""
                    
                    if not result: st.warning("此文件夹为空。")
                    
                    for f in result:
                        col1, col2 = st.columns([3, 1])
                        # 兼容文件名提取
                        fname = f.get('file_name') or f.get('name') or '未知文件'
                        fid = f.get('fid')
                        is_dir = f.get('obj_category') == 'dir' or f.get('type') == 1
                        
                        with col1: st.write(f"📄 {fname}")
                        with col2:
                            if not is_dir:
                                dl = get_download_link(share_id, fid, cookie_input)
                                if dl: st.link_button("下载", dl)
                                else: st.caption("失败")
                            else:
                                st.caption("📂 文件夹")
                else:
                    st.error("解析失败。错误日志：")
                    st.code(result)
else:
    st.info("请输入访问密码")
