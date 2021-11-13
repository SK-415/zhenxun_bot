from utils.message_builder import image
from utils.user_agent import get_user_agent
from configs.path_config import TEXT_PATH
from configs.config import NICKNAME
from typing import List
from nonebot import Driver
from pathlib import Path
import aiohttp
import ujson as json
import nonebot

driver: Driver = nonebot.get_driver()

china_city = Path(TEXT_PATH) / "china_city.json"

data = {}


async def get_weather_of_city(city: str) -> str:
    code = _check_exists_city(city)
    if code == 999:
        return "不要查一个省份的天气啊，很累人的！"
    elif code == 998:
        return f"{NICKNAME}没查到!!试试查火星的天气？"
    else:
        async with aiohttp.ClientSession(headers=get_user_agent()) as session:
            async with session.get(
                f"http://wthrcdn.etouch.cn/weather_mini?city={city}", timeout=5
            ) as res:
                data_json = json.loads(await res.text(encoding="utf8"))
                if "desc" in data_json:
                    if data_json["desc"] == "invilad-citykey":
                        return f"{NICKNAME}没查到!!试试查火星的天气？" + image(
                            "shengqi", "zhenxun"
                        )
                    elif data_json["desc"] == "OK":
                        w_type = data_json["data"]["forecast"][0]["type"]
                        w_max = data_json["data"]["forecast"][0]["high"][3:]
                        w_min = data_json["data"]["forecast"][0]["low"][3:]
                        fengli = data_json["data"]["forecast"][0]["fengli"][9:-3]
                        ganmao = data_json["data"]["ganmao"]
                        fengxiang = data_json["data"]["forecast"][0]["fengxiang"]
                        repass = f"{city}的天气是 {w_type} 天\n最高温度: {w_max}\n最低温度: {w_min}\n风力: {fengli} {fengxiang}\n{ganmao}"
                        return repass
                else:
                    return "好像出错了？"


# 城市是否存在或是否是省份
def _check_exists_city(city: str) -> int:
    global data
    city = city if city[-1] != "市" else city[:-1]
    for province in data.keys():
        for city_ in data[province]:
            if city_ == city:
                return 200
    for province in data.keys():
        if city == province:
            return 999
    return 998


def get_city_list() -> List[str]:
    global data
    if not data:
        try:
            with open(china_city, "r", encoding="utf8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
    city_list = []
    for p in data.keys():
        for c in data[p]:
            city_list.append(c)
        city_list.append(p)
    return city_list
