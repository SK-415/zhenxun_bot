from configs.path_config import IMAGE_PATH, TXT_PATH
from services.log import logger
from datetime import datetime
from utils.image_utils import compressed_image, get_img_hash
from utils.utils import get_bot, get_local_proxy
from asyncio.exceptions import TimeoutError
from models.setu import Setu
from aiohttp.client_exceptions import ClientConnectorError
from asyncpg.exceptions import UniqueViolationError
from pathlib import Path
from nonebot import Driver
import nonebot
import aiofiles
import aiohttp
import os
import ujson as json

driver: Driver = nonebot.get_driver()

_path = Path(IMAGE_PATH)


@driver.on_startup
async def update_old_setu_data():
    path = Path(TXT_PATH)
    setu_data_file = path / "setu_data.json"
    r18_data_file = path / "r18_setu_data.json"
    if setu_data_file.exists() or r18_data_file.exists():
        index = 0
        r18_index = 0
        count = 0
        fail_count = 0
        for file in [setu_data_file, r18_data_file]:
            if file.exists():
                data = json.load(open(file, "r", encoding="utf8"))
                for x in data:
                    if file == setu_data_file:
                        idx = index
                        if 'R-18' in data[x]["tags"]:
                            data[x]["tags"].remove('R-18')
                    else:
                        idx = r18_index
                    img_url = (
                        data[x]["img_url"].replace("i.pixiv.cat", "i.pximg.net")
                        if "i.pixiv.cat" in data[x]["img_url"]
                        else data[x]["img_url"]
                    )
                    # idx = r18_index if 'R-18' in data[x]["tags"] else index
                    try:
                        await Setu.add_setu_data(
                            idx,
                            data[x]["title"],
                            data[x]["author"],
                            data[x]["pid"],
                            data[x]["img_hash"],
                            img_url,
                            ",".join(data[x]["tags"]),
                        )
                        count += 1
                        if 'R-18' in data[x]["tags"]:
                            r18_index += 1
                        else:
                            index += 1
                        logger.info(f'添加旧色图数据成功 PID：{data[x]["pid"]} index：{idx}....')
                    except UniqueViolationError:
                        fail_count += 1
                        logger.info(f'添加旧色图数据失败，色图重复 PID：{data[x]["pid"]} index：{idx}....')
                file.unlink()
        setu_url_path = path / "setu_url.json"
        setu_r18_url_path = path / "setu_r18_url.json"
        if setu_url_path.exists():
            setu_url_path.unlink()
        if setu_r18_url_path.exists():
            setu_r18_url_path.unlink()
        logger.info(f"更新旧色图数据完成，成功更新数据：{count} 条，累计失败：{fail_count} 条")


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6;"
    " rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
    "Referer": "https://www.pixiv.net",
}


async def update_setu_img():
    image_list = await Setu.get_all_setu()
    image_list.reverse()
    _success = 0
    error_info = []
    error_type = []
    count = 0
    async with aiohttp.ClientSession(headers=headers) as session:
        for image in image_list:
            count += 1
            path = _path / "_r18" if image.is_r18 else _path / "_setu"
            rar_path = "r18_rar" if image.is_r18 else "rar"
            local_image = path / f"{image.local_id}.jpg"
            if not local_image.exists() or not image.img_hash:
                for _ in range(3):
                    try:
                        async with session.get(
                            image.img_url, proxy=get_local_proxy(), timeout=30
                        ) as response:
                            if response.status == 200:
                                async with aiofiles.open(
                                    f"{IMAGE_PATH}/{rar_path}/{image.local_id}.jpg",
                                    "wb",
                                ) as f:
                                    await f.write(await response.read())
                                    _success += 1
                                try:
                                    if (
                                        os.path.getsize(
                                            f"{IMAGE_PATH}/{rar_path}/{image.local_id}.jpg"
                                        )
                                        > 1024 * 1024 * 1.5
                                    ):
                                        compressed_image(
                                            os.path.join(
                                                rar_path, f"{image.local_id}.jpg"
                                            ),
                                            os.path.join(path, f"{image.local_id}.jpg"),
                                        )
                                    else:
                                        logger.info(
                                            f"不需要压缩，移动图片 {IMAGE_PATH}/{rar_path}/{image.local_id}.jpg "
                                            f"--> /{path}/{image.local_id}.jpg"
                                        )
                                        os.rename(
                                            f"{IMAGE_PATH}/{rar_path}/{image.local_id}.jpg",
                                            f"{path}/{image.local_id}.jpg",
                                        )
                                except FileNotFoundError:
                                    logger.warning(f"文件 {image.local_id}.jpg 不存在，跳过...")
                                    _success -= 1
                                    continue
                                img_hash = str(
                                    get_img_hash(
                                        f"{path}/{image.local_id}.jpg"
                                    )
                                )
                                await Setu.update_setu_data(
                                    image.pid, img_hash=img_hash
                                )
                                break
                    except (TimeoutError, ClientConnectorError) as e:
                        logger.warning(f"{image.local_id}.jpg 更新失败 ..{type(e)}：{e}")
                    except Exception as e:
                        _success -= 1
                        logger.error(f"更新色图 {image.local_id}.jpg 错误 {type(e)}: {e}")
                        if type(e) not in error_type:
                            error_type.append(type(e))
                            error_info.append(
                                f"更新色图 {image.local_id}.jpg 错误 {type(e)}: {e}"
                            )
            else:
                logger.info(f'更新色图 {image.local_id}.jpg 已存在')
    error_info = ['无报错..'] if not error_info else error_info
    await get_bot().send_private_msg(
        user_id=int(list(get_bot().config.superusers)[0]),
        message=f'{str(datetime.now()).split(".")[0]} 更新 色图 完成，本地存在 {count} 张，实际更新 {_success} 张，以下为更新时未知错误：\n'
        + "\n".join(error_info),
    )


