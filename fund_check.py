import requests
import os
import json

# 在这里填写你的基金代码，可自行增减
fund_codes = ["001606", "110011", "161725"]

server_key = os.getenv("SERVERCHAN_KEY")
push_url = f"https://sctapi.ftqq.com/{server_key}.send"

def get_fund_data(code):
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    res = requests.get(url, timeout=10)
    text = res.text
    data_json = json.loads(text.strip("jsonpgz();"))
    name = data_json["name"]
    gsz = data_json["gsz"]
    gszzfr = data_json["gszzl"]
    time = data_json["gztime"]
    return f"{name}\n净值：{gsz}\n涨幅：{gszzfr}%\n更新时间：{time}"

def main():
    content = "📊 基金每日收盘提醒\n" + "="*20 + "\n"
    for code in fund_codes:
        try:
            content += get_fund_data(code) + "\n" + "-"*15 + "\n"
        except:
            content += f"基金{code}获取失败\n"
    params = {"title":"基金行情提醒", "desp":content}
    requests.post(push_url, data=params)

if __name__ == "__main__":
    main()
