import os
import time
import json
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import Bot, InputMediaPhoto

from db import load_sent_ids, save_sent_id, ensure_table_exists

# Telegram конфигурация через переменные окружения
YOUR_TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
YOUR_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
bot = Bot(token=YOUR_TELEGRAM_BOT_TOKEN)

# OLX ссылки
OLX_URLS = [
    "https://www.olx.ua/uk/list/q-canon-ixus/?search%5Bfilter_float_price:to%5D=5000&search%5Bfilter_enum_digital_camera_manufacturers%5D%5B0%5D=2580",
    "https://www.olx.ua/uk/list/q-canon-elph/?search%5Border%5D=created_at:desc&search%5Bfilter_float_price:to%5D=5000&search%5Bfilter_enum_digital_camera_manufacturers%5D%5B0%5D=2580"
]

# Приоритетные модели
PRIORITY_MODELS = ['135', '160', '175', '185', '190', '220']

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

def get_all_images_from_ad(url, driver, retries=2):
    for attempt in range(retries):
        try:
            driver.set_page_load_timeout(60)
            driver.get(url)

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'img[data-testid="swiper-image"]'))
            )

            soup = BeautifulSoup(driver.page_source, "html.parser")
            script_tag = soup.find("script", type="application/ld+json")

            if not script_tag:
                logging.warning(f"⚠️ Не знайдено JSON-LD скрипт на сторінці {url}")
                return []

            data = json.loads(script_tag.string)
            images = data.get("image", [])
            if isinstance(images, str):
                return [images]
            elif isinstance(images, list):
                return images
            else:
                return []
        except Exception as e:
            logging.error(f"⚠️ Помилка при отриманні фото через JSON-LD: {e}")
            time.sleep(1)
    return []

def send_telegram_group(ad_id, title, price, date, url, photo_urls, priority=False):
    if priority:
        title = f"🔥 ПРІОРИТЕТ | {title}"

    text = f"<b>{title}</b>\nЦіна: {price}\nДата: {date}\n\n<a href='{url}'>Переглянути оголошення</a>"

    try:
        if photo_urls:
            photo_urls = photo_urls[:10]
            if len(photo_urls) == 1:
                bot.send_photo(chat_id=YOUR_CHAT_ID, photo=photo_urls[0], caption=text, parse_mode="HTML")
            else:
                media = [InputMediaPhoto(media=img) for img in photo_urls]
                media[0].caption = text
                media[0].parse_mode = "HTML"
                bot.send_media_group(chat_id=YOUR_CHAT_ID, media=media)
        else:
            bot.send_message(chat_id=YOUR_CHAT_ID, text=text, parse_mode="HTML")

        logging.info(f"✅ Надіслано: {title}")
        save_sent_id(ad_id)
    except Exception as e:
        logging.error(f"❌ Помилка при відправці в Telegram: {e}")

def is_priority(title):
    return any(model in title for model in PRIORITY_MODELS)

def main():
    logging.info("🚀 Запуск моніторингу OLX...")

    ensure_table_exists()
    sent_ids = load_sent_ids()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        while True:
            priority_ads = []
            other_ads = []

            for url in OLX_URLS:
                driver.get(url)
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-cy="l-card"]'))
                    )
                except TimeoutException:
                    logging.warning(f"⚠️ Не вдалося завантажити оголошення з {url}")
                    continue

                items = driver.find_elements(By.CSS_SELECTOR, 'div[data-cy="l-card"]')
                logging.info(f"🔍 {url} — знайдено {len(items)} оголошень (до фільтрації)")

                filtered_count = 0
                for item in items:
                    try:
                        ad_id = item.get_attribute("id")
                        if not ad_id or ad_id in sent_ids:
                            continue

                        title_el = item.find_element(By.CSS_SELECTOR, 'div[data-cy="ad-card-title"] h4')
                        price_el = item.find_element(By.CSS_SELECTOR, 'p[data-testid="ad-price"]')
                        link_el = item.find_element(By.CSS_SELECTOR, 'a.css-rc5s2u, a.css-1tqlkj0')
                        location_date_el = item.find_element(By.CSS_SELECTOR, 'p[data-testid="location-date"]')

                        title = title_el.text.strip()
                        price = price_el.text.strip()
                        location_date = location_date_el.text.strip()
                        date = location_date.split(" - ")[-1].strip() if " - " in location_date else "Невідомо"
                        link = link_el.get_attribute("href")
                        if link.startswith("/"):
                            link = "https://www.olx.ua" + link

                        if "ixus" in title.lower() or "elph" in title.lower():
                            ad_tuple = (ad_id, title, price, date, link)
                            if is_priority(title.lower()):
                                priority_ads.append(ad_tuple)
                            else:
                                other_ads.append(ad_tuple)
                            filtered_count += 1
                    except Exception as e:
                        logging.warning(f"⚠️ Проблема при розборі одного з оголошень: {e}")

                logging.info(f"✅ Після фільтрації залишилось: {filtered_count} оголошень")

            for ad_list in [priority_ads, other_ads]:
                for ad_id, title, price, date, url in ad_list:
                    try:
                        photo_urls = get_all_images_from_ad(url, driver)
                        logging.info(f"Знайдено фото: {len(photo_urls)} для {title}")
                        send_telegram_group(ad_id, title, price, date, url, photo_urls,
                                            priority=(ad_list is priority_ads))
                        sent_ids.add(ad_id)
                    except Exception as e:
                        logging.error(f"⚠️ Внутрішня помилка обробки: {e}")

            logging.info("⌛ Чекаємо 5 хвилин до наступної перевірки...\n")
            time.sleep(300)

    except KeyboardInterrupt:
        logging.info("🛑 Зупинка за Ctrl+C. До побачення!")
        driver.quit()
    except Exception as e:
        logging.exception(f"❗ Непередбачена помилка: {e}")
        driver.quit()

if __name__ == "__main__":
    main()
