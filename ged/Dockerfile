FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 ged

WORKDIR /app
COPY requirements/ requirements/
RUN pip install -r requirements/base.txt

COPY . .
RUN DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py compilemessages -l ar \
    && mkdir -p /srv/static /srv/scellements \
    && chown -R ged:ged /srv/static /srv/scellements

USER ged
EXPOSE 8000
ENTRYPOINT ["/app/docker/web/entrypoint.sh"]
CMD ["web"]
