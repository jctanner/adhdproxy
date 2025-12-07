FROM python:3

RUN apt update && apt -y install jq less ffmpeg openssl

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY flaskapp.py /app/.
COPY templates /app/.
COPY entrypoint.sh /app/.
WORKDIR /app

RUN chmod +x /app/entrypoint.sh

#ENTRYPOINT flask flaskapp.py
ENTRYPOINT ["/app/entrypoint.sh"]
