FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxrandr2 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libxss1 libxtst6 libx11-6 libxext6 libxi6 \
    libxfixes3 libxrender1 libgtk-3-0 libgbm1 xdg-utils fonts-liberation \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install && \
    rm google-chrome-stable_current_amd64.deb

RUN wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/137.0.7151.68/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PATH="/usr/local/bin:$PATH"
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
