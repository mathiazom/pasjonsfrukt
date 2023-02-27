FROM python:3.10.9-bullseye

RUN apt update && apt -y install cron && apt -y install ffmpeg

# Set local timezone (for cron)
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

# Create cron log file to be able to run tail
RUN touch /var/log/pasjonsfrukt.log

WORKDIR /app

RUN curl -sSL https://install.python-poetry.org | python3 - -y --version 1.3.1

RUN /root/.local/bin/poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

COPY pasjonsfrukt pasjonsfrukt

RUN /root/.local/bin/poetry install --only main

COPY docker/entrypoint.sh .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]