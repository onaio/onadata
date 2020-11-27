FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

RUN apt-get update -q &&\
    apt-get install -y --no-install-recommends software-properties-common \
        binutils \
        libproj-dev \
        gdal-bin \
        memcached \
        libmemcached-dev \
        build-essential \
        python3.6 \
        python3.6-dev \
        python3-pip \
        virtualenv \
        git \
        libssl-dev \
        libpq-dev \
        gfortran \
        libatlas-base-dev \
        libjpeg-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        ghostscript \
        python-celery \
        python-sphinx \
        pkg-config \
        gcc \
        automake \
        libtool \
        openjdk-11-jre-headless \
        locales \
        tmux && \
    rm -rf /var/lib/apt/lists/*

RUN locale-gen en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
RUN dpkg-reconfigure locales

RUN useradd -m onadata
RUN mkdir -p /srv/onadata && chown -R onadata:onadata /srv/onadata

USER onadata

COPY . /srv/onadata

WORKDIR /srv/onadata/

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

# Configure Tmux to use bash shell
RUN echo "set-option -g default-shell /bin/bash" > ~/.tmux.conf

CMD ["/srv/onadata/docker/docker-entrypoint.sh"]