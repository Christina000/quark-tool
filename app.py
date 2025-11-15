import streamlit as st
import requests
import re
import json

st.set_page_config(page_title="夸克直链解析 (Debug修复版)", layout="centered")

# 伪装头
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_files_from_api(share_url, cookie, pwd_code=""):
    # 1. 提取 pwd_id (share_id)
    try:
        # 兼容两种链接格式：s/xxxx?pwd=yyy 和 s/xxxx
        match = re.search(r"s/([a-zA-Z0-9]+)", share_url)
        if not match:
            return False, "链接格式错误，未找到分享ID (s/后面那串)"
        pwd_id = match.group(1)
    except Exception as e:
        return False, f"链接解析错误: {str(e)}"

    # 2. 准备 API 请求
    # 修正点：接口从 /dir 改为 /sort，域名用 pan.quark.cn
    api_url = "https://pan.quark.cn/1/clouddrive/share/share_page/sort?pr=ucpro&fr=pc"
    
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie.strip(),
        "Referer": "https://pan.quark.cn/",
        "Origin": "https://pan.quark.cn",
        "Accept": "application/json, text/plain, */*"
    }

    # 修正点：sort 接口需要分页参数 _page, _size
    payload = {
        "pwd_id": pwd_id,
        "dir_fid": "0",
        "pdir_fid": "0",
        "force": 0,
        "sort_type": 6, # 按时间排序
        "_page": 1,
        "_size": 50
    }
    
    # 如果有提取码，虽然 API 逻辑复杂，但我们可以尝试传进去
    if pwd_code:
        payload["passcode"] = pwd_code

    # 3. 发送请求 (调试模式：打印详情)
    try:
        r = requests.post(api_url, headers=headers, json=payload, timeout=10)
        
        # 如果是 200 OK，说明路通了
        if r.status_code == 200:
            data = r.json()
            # 检查业务逻辑是否成功
            if data.get("code") == 0 and "list" in data.get("data", {}):
                return True, data["data"]["list"]
            else:
                # 返回具体的错误信息
                return False, f"API请求成功但返回错误: {json.dumps(data, ensure_ascii=False)}"
        else:
            return False, f"HTTP错误: {r.status_code} - {r.text}"

    except Exception as e:
        return False, f"请求异常: {str(e)}"

def get_download_link(share_id, fid, cookie):
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

# --- 界面部分 ---
st.title("夸克直链解析 (404修复版)")

pwd = st.text_input("访问密码", type="password")

if pwd == "888888":
    cookie_input = st.text_area("夸克 Cookie (必填)", height=100, placeholder="粘贴 __puus 开头的完整 Cookie")
    link_input = st.text_input("分享链接", placeholder="https://pan.quark.cn/s/...")
    
    if st.button("开始解析"):
        if not cookie_input or not link_input:
            st.error("请填写完整信息")
        else:
            # 尝试提取链接里的提取码
            pwd_code = ""
            pwd_match = re.search(r"pwd=([a-zA-Z0-9]+)", link_input)
            if pwd_match:
                pwd_code = pwd_match.group(1)

            with st.spinner("正在请求夸克 API..."):
                success, result = get_files_from_api(link_input, cookie_input, pwd_code)
                
                if success:
                    st.success("🎉 获取文件列表成功！")
                    files = result
                    # 提取 share_id 用于下载
                    share_id_match = re.search(r"s/([a-zA-Z0-9]+)", link_input)
                    share_id = share_id_match.group(1) if share_id_match else ""

                    for f in files:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📄 **{f['file_name']}** ({f.get('size_str', '未知大小')})")
                        with col2:
                            # 只有文件(非文件夹)才显示下载
                            if f.get('obj_category') != 'dir': 
                                dl_link = get_download_link(share_id, f['fid'], cookie_input)
                                if dl_link:
                                    st.link_button("⬇️ 点击下载", dl_link)
                                else:
                                    st.caption("获取链接失败")
                            else:
                                st.caption("📂 文件夹 (暂不支持递归)")
                else:
                    st.error(result)
                    # 调试信息：如果失败，显示一下刚才用的是什么参数
                    st.json({"提示": "请检查Cookie是否失效", "错误详情": result})
else:
    st.info("请输入访问密码 888888")