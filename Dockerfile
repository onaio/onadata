FROM ubuntu:20.04

# Silence configuration prompts
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

# Install service dependencies
# hadolint ignore=DL3008
RUN apt-get update -q &&\
    apt-get install -y --no-install-recommends software-properties-common \
        binutils \
        libproj-dev \
        gdal-bin \
        memcached \
        libmemcached-dev \
        build-essential \
        supervisor \
        python3.9 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        git \
        libssl-dev \
        libpq-dev \
        gfortran \
        libatlas-base-dev \
        libjpeg-dev \
        libxml2-dev \
        libxslt1-dev \
        libpython3.9-dev \
        zlib1g-dev \
        ghostscript \
        python3-celery \
        python3-sphinx \
        pkg-config \
        gcc \
        automake \
        libtool \
        openjdk-11-jre-headless \
        libpcre3 \
        libpcre3-dev \
        locales \
        netcat && \
    apt-get -y -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold' dist-upgrade &&\
    rm -rf /var/lib/apt/lists/*

# Generate and set en_US.UTF-8 locale
RUN locale-gen en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
RUN dpkg-reconfigure locales

# Create OnaData user and add to tty group
RUN useradd -G tty -m onadata

# Make app directory
RUN mkdir -p /srv/onadata && chown -R onadata:onadata /srv

# Copy local codebase
COPY . /srv/onadata

# Install service requirements
# hadolint ignore=DL3013
RUN python3.9 -m pip install --no-cache-dir -U pip && \
    python3.9 -m pip install --no-cache-dir -r /srv/onadata/requirements/base.pip && \
    python3.9 -m pip install --no-cache-dir -r /srv/onadata/requirements/s3.pip && \
    python3.9 -m pip install --no-cache-dir -r /srv/onadata/requirements/ses.pip && \
    python3.9 -m pip install --no-cache-dir -r /srv/onadata/requirements/azure.pip && \
    python3.9 -m pip install --no-cache-dir uwsgitop django-silk

WORKDIR /srv/onadata

EXPOSE 8000

USER onadata

CMD ["/usr/local/bin/uwsgi", "--ini", "/srv/onadata/uwsgi.ini"]
