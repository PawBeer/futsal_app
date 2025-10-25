from python:3.12-slim-bullseye


WORKDIR /usr/src/app
COPY requirements.txt ./

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
    sqlite3 \
    && pip install -r requirements.txt \
    && apt autoremove -y && apt clean \
	&& rm -rf /var/lib/apt/lists/*

COPY . .

# copies/generates all the static file to the folder STATIC_ROOT from settings.py
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["python", "manage.py", "runserver",  "0.0.0.0:8000"]
