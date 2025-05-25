from flask import Flask, render_template, request
import requests
import matplotlib.pyplot as plt
import os
import matplotlib
matplotlib.use('Agg')  # 不使用 X-window 後端
matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 原本的 API 設定與程式邏輯都可以保留（稍微包成函數）
CITY_API = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001'
DISTRICT_API = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-093'
API_KEY = 'CWA-F672F228-AA9D-4184-8976-269CD9D19B0C'

app = Flask(__name__)

def is_district(location):
    return location.endswith("區") or location.endswith("鄉") or location.endswith("鎮") or location in ["新竹市", "嘉義市"]

def generate_advice(weather, rain_prob, temp):    
    return f"天氣：{weather}，降雨機率 {rain_prob}% ，溫度約 {temp}°C，請酌情穿著並攜帶雨具。"

def fetch_city_data(location, time_filter):
    res = requests.get(CITY_API, params={'Authorization': API_KEY, 'locationName': location})
    data = res.json()
    location_data = data['records']['location'][0]
    name = location_data['locationName']
    elements = {e['elementName']: e['time'] for e in location_data['weatherElement']}
    count = min(len(elements['Wx']), len(elements['PoP']), len(elements['MinT']), len(elements['MaxT']), 4)
    results = []
    for i in range(count):
        start = elements['Wx'][i]['startTime']
        hour = int(start[11:13])
        period = "白天" if hour == 6 else "夜間"
        if time_filter != "全部" and time_filter != period:
            continue
        weather = elements['Wx'][i]['parameter']['parameterName']
        rain = int(elements['PoP'][i]['parameter']['parameterName'])
        tmin = int(elements['MinT'][i]['parameter']['parameterName'])
        tmax = int(elements['MaxT'][i]['parameter']['parameterName'])
        avg = round((tmin + tmax) / 2)
        results.append({
            "時間": f"{start} ~ {elements['Wx'][i]['endTime']}（{period}）",
            "天氣": weather,
            "降雨機率": f"{rain}%",
            "溫度": f"{avg}°C",
            "建議": generate_advice(weather, rain, avg)
        })
    return name, results

def fetch_district_data(location, time_filter):
    res = requests.get(DISTRICT_API, params={
        'Authorization': API_KEY,
        'locationName': location,
        'elementName': 'WeatherDescription,PoP12h,T'
    })
    data = res.json()
    location_data = data['records']['locations'][0]['location'][0]
    name = location_data['locationName']
    elements = {e['elementName']: e['time'] for e in location_data['weatherElement']}
    count = min(len(elements['WeatherDescription']), len(elements['PoP12h']), len(elements['T']), 8)
    results = []
    for i in range(count):
        start = elements['WeatherDescription'][i]['startTime']
        hour = int(start[11:13])
        if 5 <= hour < 11:
            period = "早上"
        elif 11 <= hour < 17:
            period = "中午"
        else:
            period = "晚上"
        if time_filter != "全部" and time_filter != period:
            continue
        weather = elements['WeatherDescription'][i]['elementValue'][0]['value']
        rain = int(elements['PoP12h'][i]['elementValue'][0]['value'])
        temp = int(elements['T'][i]['elementValue'][0]['value'])
        results.append({
            "時間": f"{start} ~ {elements['WeatherDescription'][i]['endTime']}（{period}）",
            "天氣": weather,
            "降雨機率": f"{rain}%",
            "溫度": f"{temp}°C",
            "建議": generate_advice(weather, rain, temp)
        })
    return name, results

def generate_chart(forecast, location):
    times = [f["時間"].split(" ")[0] + f["時間"].split("（")[-1].replace("）", "") for f in forecast]
    temps = [float(f["溫度"].replace("°C", "")) for f in forecast]
    rain_probs = [int(f["降雨機率"].replace("%", "")) for f in forecast]

    plt.figure(figsize=(10, 6))
    plt.plot(times, temps, 'b-o', label='平均溫度 (°C)', linewidth=2, markersize=6)
    plt.bar(times, rain_probs, color='lightblue', alpha=0.6, label='降雨機率 (%)')

    for i, (t, r) in enumerate(zip(times, rain_probs)):
        plt.text(i, r + 1, f"{r}%", ha='center', fontsize=9)
    for i, (t, temp) in enumerate(zip(times, temps)):
        plt.text(i, temp + 0.5, f"{temp}°", ha='center', fontsize=9, color='blue')

    plt.title(f'{location} 未來天氣預報')
    plt.xlabel('時間')
    plt.ylabel('溫度 / 降雨機率')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    os.makedirs("static", exist_ok=True)
    chart_path = os.path.join("static", "weather_forecast.png")
    plt.savefig(chart_path)
    plt.close()
    return chart_path

@app.route("/", methods=["GET", "POST"])
def index():
    forecast = []
    location_name = ""
    chart_path = None
    if request.method == "POST":
        location = request.form["location"].strip()
        time_filter = request.form["time"].strip()
        if is_district(location):
            location_name, forecast = fetch_district_data(location, time_filter)
        else:
            location_name, forecast = fetch_city_data(location, time_filter)
        if forecast:
            chart_path = generate_chart(forecast, location)
    return render_template("index.html", forecast=forecast, location=location_name, chart=chart_path)

if __name__ == "__main__":
    app.run(debug=True)