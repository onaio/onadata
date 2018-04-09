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
    locales

RUN  locale-gen en_US.UTF-8
RUN mkdir -p /srv/onadata/requirements

ADD requirements /srv/onadata/requirements/

WORKDIR /srv/onadata

RUN virtualenv /srv/.virtualenv
RUN . /srv/.virtualenv/bin/activate; \
    pip install pip --upgrade && pip install -r requirements/base.pip

ADD . /srv/onadata/

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

RUN rm -rf /var/lib/apt/lists/* \
  && find . -name '*.pyc' -type f -delete

CMD ["/srv/onadata/docker/docker-entrypoint.sh"]
