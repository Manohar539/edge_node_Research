FROM python:3.13-slim

WORKDIR /app

COPY controller/requirements.txt ./controller/requirements.txt

RUN pip install --no-cache-dir -r controller/requirements.txt

COPY controller ./controller
COPY shared ./shared
COPY config ./config

CMD ["python", "-u", "-m", "controller.real_controller"]