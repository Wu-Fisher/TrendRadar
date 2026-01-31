FROM python:3.10-slim

WORKDIR /app

# 复制本地 supercronic 文件（避免网络下载问题）
COPY docker/supercronic-linux-amd64 /usr/local/bin/supercronic-linux-amd64
RUN chmod +x /usr/local/bin/supercronic-linux-amd64 && \
    ln -s /usr/local/bin/supercronic-linux-amd64 /usr/local/bin/supercronic && \
    supercronic -version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/manage.py .
COPY trendradar/ ./trendradar/
COPY scripts/ ./scripts/

# 复制 entrypoint.sh 并强制转换为 LF 格式
COPY docker/entrypoint.sh /entrypoint.sh.tmp
RUN sed -i 's/\r$//' /entrypoint.sh.tmp && \
    mv /entrypoint.sh.tmp /entrypoint.sh && \
    chmod +x /entrypoint.sh && \
    chmod +x manage.py && \
    mkdir -p /app/config /app/output /root/.local/share/TrendRadar

ENV PYTHONUNBUFFERED=1 \
    CONFIG_PATH=/app/config/config.yaml \
    FREQUENCY_WORDS_PATH=/app/config/frequency_words.txt

ENTRYPOINT ["/entrypoint.sh"]