FROM python:3

RUN apt update && apt -y install jq less ffmpeg

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY flaskapp.py /app/.
COPY templates /app/.
WORKDIR /app

#ENTRYPOINT flask flaskapp.py
ENTRYPOINT python flaskapp.py
