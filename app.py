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
    cookie_input = st.text_area("__puus=d36f1fc1f73a7055405c271cbed6d31aAAQe8H1ldyuN0XHjk/9LwXPCBE49q9/akP/vA1+f0u4ezoQ9hz2WGaHIReqCIjxNV1QvjeetzEwofluxHneusuVT0cnimk96RvtpQFSy0wxTFySn9nPwjkHxKuXOhJEmSJ46sLB3N0NYtOzX8qbauc31zsGIEx2JAFjLws4Q5JmksMNb3ZwfxSiqxxgMAsPyjKi4iMo6R0S325BtFCAShOAc; tfstk=gIMsEAAzlqHUIvc81--FNhk9ZBw0CHJy5iZxqmBNDRetD-gQ8l5wsS8jOq3UW-la7oUQJ2nNQryThng3BScauPzbhm07fUJyUcmgnRLyzLkpQv2YEZCYXZWLvoebX0VRCCngn-LFYtdyFc0a6P1QM-KQpoq5k-FTWkKQ0oEYHPFAJ6E8Jrexk5QLplqbkZUTW9KQmyUYH-3xvHZ4JreYHqnpONBLYianf3DWfLYl7-mTRtBxB-V_VxfVhtizXD1iXyisfvZ_1zNbV9cnF0ntEoMD2sabWfh8BxT5uWgK6bethU_Lofrl4eBzP9x1GMNlHk1MAH1cizdAzzuRP1tQ6kqE2HtCaOVTxkayAH1ci5E3Y0KBA_WG.; __kp=f469b270-c1e3-11f0-b429-676789c4bad4; __kps=AAQHCWvhef7sP8Qhsl9RX11S; __ktd=K+D1HCWKjg8GZ012pL1mbQ==; __pus=e009b32a451a0f394297fb9e5300ca6dAASbPFv9KdK2v+BSPlYa1B+fyi+FDwZQYOEzW0dQkk79hd68QfNFwcw2KFxnWyGiPjmxPOOHH0zBL4C3/r6+Mbdg; __uid=AAQHCWvhef7sP8Qhsl9RX11S; _UP_D_=pc; _UP_F7E_8D_=YNpFifoXeIQDA44MlTNyuBzy6ZfcuPaCcCX5PS4jd7Zw5svFZsD9Sz5wmccE2Csl1oAP1ZRm6y%2BAumlMbX52H006Voi4Cemlwh0Ex05IZj3%2FRaBK%2BCNsP60zJJQqu5vYeRot5mpnzxIQkIV6RIDEGlWVKuUD8cTfTXkFjVYxrBym5aiHCgEwQssH4vzcOfSUgOHfqGdFx%2BVb9AlhXg01Ow3dFTisAZohxTl7erHipNAts96g52ErQX7gJXHB34DmTJyVbneFy5M6bSold6u4KyvhKuNlIF0H%2BpUFs0q3c3ZpyUwjEH3sDbo0FnDdrt5TgicLGXWDULSzVjEvMmznaVZ2giTX2e9Z%2FK0%2FzVwkrF%2B%2FUZ%2FAFOtHRtL8Ea33V8aFkzDJm84ptT%2FxmRuCsa%2BbDGrOK%2BW7NepAeuYdTBrH19WVzMQZ1GracmRKLnouDIOtemzJh0ZgDQXgKP%2Be2vzS%2BRRNxrkTQuotwES3hQ3qMNg%3D; web-grey-id=490311c3-f7d8-d6ae-9eff-4779423f8bac; web-grey-id.sig=Gyk6alBPXoGBemrSThVcs2xo3j9AoQWgC1l0EQw0zU0; _UP_A4A_11_=wb9cf12e7ab2480499c3d898c5e991ed; __wpkreporterwid_=e025dfe2-5e9f-417f-1c4b-c21f29d38ef5; b-user-id=95f8027c-aeed-e575-7c0e-d270615f626f; ctoken=KKda_Vr0MxOtJHH6W2oUZ1iM; grey-id=24be2c38-610b-b169-3916-8e669a2571b7; grey-id.sig=wIsqAAC-uuBtCb1sHNPfEUPLMGJyp1jFFMV1izwS-VQ; isQuark=true; isQuark.sig=hUgqObykqFom5Y09bll94T1sS9abT1X-4Df_lzgl8nM", height=100)
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
