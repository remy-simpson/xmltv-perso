FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
COPY wheels /wheels
ARG PIP_NO_INDEX=0
RUN pip install --no-cache-dir --find-links=/wheels -r requirements.txt
COPY --chown=10001:10001 server.py .
COPY --chown=10001:10001 public ./public
RUN useradd --uid 10001 --create-home onde && mkdir /app/data && chown onde /app/data
USER onde
ENV HOST=0.0.0.0 PORT=3000 ONDE_DATA=/app/data
EXPOSE 3000
CMD ["python", "server.py"]
