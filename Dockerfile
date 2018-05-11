FROM ubuntu:16.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
  && apt-get install -y postgresql-client \
    libproj-dev \
    gdal-bin \
    memcached \
    libmemcached-dev \
    build-essential \
    python-pip \
    python-virtualenv \
    python-dev \
    git \
    libssl-dev \
    libpq-dev \
    gfortran \
    libatlas-base-dev \
    libjpeg-dev \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    python-software-properties \
    ghostscript \
    python-celery \
    python-sphinx \
    openjdk-9-jre-headless \
    python-virtualenv \
    locales \
    pkg-config \
    gcc \
    libtool \
    automake

RUN  locale-gen en_US.UTF-8

RUN useradd -m onadata
RUN mkdir -p /srv/onadata && chown -R onadata:onadata /srv/onadata
USER onadata
RUN mkdir -p /srv/onadata/requirements

ADD requirements /srv/onadata/requirements/

WORKDIR /srv/onadata

RUN virtualenv /srv/onadata/.virtualenv
RUN . /srv/onadata/.virtualenv/bin/activate; \
    pip install pip --upgrade && pip install -r requirements/base.pip

ADD . /srv/onadata/

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

USER root

# for local development tmux is a nice to have
RUN apt-get install -y tmux \
    && echo "set-option -g default-shell /bin/bash" > ~/.tmux.conf

RUN rm -rf /var/lib/apt/lists/* \
  && find . -name '*.pyc' -type f -delete
USER onadata

CMD ["/srv/onadata/docker/docker-entrypoint.sh"]
