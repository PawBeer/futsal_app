from python:3.12-slim-bullseye


WORKDIR /usr/src/app
COPY requirements.txt ./

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
    sqlite3 \
    && pip install -r requirements.txt \
    && apt autoremove -y && apt clean \
	&& rm -rf /var/lib/apt/lists/*

# Skopiuj resztę aplikacji
COPY . .

# Utwórz katalog dla collectstatic (WhiteNoise użyje STATIC_ROOT)
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["python", "manage.py", "runserver",  "0.0.0.0:8000"]
