import logging
import os
import uuid

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.auth_data = (
            os.getenv("GIGACHAT_AUTH_DATA", "")
            .strip()
            .replace('"', "")
            .replace("'", "")
        )
        self.api_url = (
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        )
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    def get_access_token(self):
        """Получает временный токен доступа."""
        r_uid = str(uuid.uuid4())

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {self.auth_data}",
            "RqUID": r_uid,
        }

        payload = {"scope": "GIGACHAT_API_PERS"}

        try:
            response = requests.post(
                self.token_url,
                headers=headers,
                data=payload,
                verify=False,
                timeout=10,
            )

            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(
                    f"GigaChat Auth Error {response.status_code}:"
                    + f" {response.text}"
                )
                print(f"Детали ошибки Сбера: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Сетевая ошибка при получении токена: {e}")
            return None

    def complete(self, prompt: str) -> str:
        token = self.get_access_token()
        if not token:
            return "Следы затерялись в тумане..."

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        payload = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты — автор нуарных детективов."
                    + " Пиши кратко, до 7 слов, только на русском языке.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 50,
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=20,
            )
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()

            logger.error(f"GigaChat API Error: {response.status_code}")
            return "Улика скрыта во тьме..."
        except Exception as e:
            logger.error(f"GigaChat Connection Error: {e}")
            return "Никаких зацепок..."

    def generate_clue(self, traits_str: str) -> str:
        """Генерирует улику на основе примет (только строка)"""
        instruction = (
            f"Приметы подозреваемого: {traits_str}. "
            "Напиши ОДНУ улику (5-8 слов) на русском языке. "
            "КЛЮЧЕВЫЕ ЗАПРЕТЫ (НИ В КОЕМ СЛУЧАЕ НЕ НАРУШАТЬ): "
            "- НЕЛЬЗЯ называть ЛЮБЫЕ ПРЕДМЕТЫ (кольцо, часы, очки, сумка и тд)"
            "- НЕЛЬЗЯ называть ЛЮБЫЕ ЧАСТИ ТЕЛА (волосы, руки, ноги и тд)"
            "- НЕЛЬЗЯ называть ЛЮБЫЕ ЦВЕТА (чёрный, белый, красный, синий) "
            "- НЕЛЬЗЯ называть ОДЕЖДУ (куртка, платье, брюки, каблуки) "
            "- НЕЛЬЗЯ использовать слова ИЗ ПРИМЕТ (даже в других формах) "
            "РАЗРЕШЕНО использовать ТОЛЬКО: "
            "- абстрактные звуки (шаг, стук, шорох, вздох, кашель, скрип) "
            "- атмосферу (холод, сырость, темнота, тишина, пустота, мрак) "
            "- время (полночь, рассвет, сумерки, ночь) "
            "- ощущения (дрожь, тревога, покой, страх) "
            "- действия (мелькнуло, исчезло, замерло, раздалось) "
            "ПРИМЕРЫ (обучающие): "
            "Примета 'высокий рост' → 'Длинная тень исчезла во тьме.' "
            "Примета 'чёрные волосы' → 'В темноте что-то мелькнуло и пропало.'"
            "Примета 'кожаная куртка' → 'Скрип кожи затих в переулке.' "
            "Примета 'каблуки' → 'Шаги замерли у порога.' "
            "Примета 'очки' → 'Что-то блеснуло в лунном свете.' "
            "Примета 'кольцо' → 'Что-то сверкнуло и упало во тьму.' "
            "Напиши ТОЛЬКО улику, без кавычек и пояснений."
        )
        return self.complete(instruction)


def get_llm_client() -> LLMClient:
    return LLMClient()
