FROM python:3.12-slim

# Noto Sans CJK is the font the renderer looks for (find_font in generate.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/
RUN chmod +x /app/entrypoint.sh

ENV TZ=Asia/Tokyo \
    OUT_PATH=/data/dashboard.png \
    REMINDERS_FILE=/data/reminders.json \
    DATA_DIR=/data \
    PORT=8080

VOLUME ["/data"]
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
