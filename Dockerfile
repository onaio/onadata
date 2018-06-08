FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
  && apt-get install -y postgresql-client \
    libproj-dev \
    gdal-bin \
    memcached \
    libmemcached-dev \
    build-essential \
    python3.6-dev \
    python3.6-venv \
    git \
    libssl-dev \
    libpq-dev \
    gfortran \
    libatlas-base-dev \
    libjpeg-dev \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    ghostscript \
    python-celery \
    python-sphinx \
    openjdk-8-jre \
    locales \
    pkg-config \
    gcc \
    libtool \
    automake

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8

RUN useradd -m onadata
RUN mkdir -p /srv/onadata && chown -R onadata:onadata /srv
USER onadata

COPY . /srv/onadata
WORKDIR /srv/onadata

RUN python3.6 -m venv /srv/.virtualenv \
  && /srv/.virtualenv/bin/pip install pip --upgrade  \
  && /srv/.virtualenv/bin/pip install -r requirements/base.pip

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

CMD ["/srv/onadata/docker/docker-entrypoint.sh"]
