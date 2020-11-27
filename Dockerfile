FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

RUN apt-get update -q &&\
    apt-get install -y --no-install-recommends software-properties-common=0.96.24.32.14 \
        binutils=2.30-21ubuntu1~18.04.4 \
        libproj-dev=4.9.3-2 \
        gdal-bin=2.2.3+dfsg-2 \
        memcached=1.5.6-0ubuntu1.2 \
        libmemcached-dev=1.0.18-4.2ubuntu0.18.04.1 \
        build-essential=12.4ubuntu1 \
        python3.6=3.6.9-1~18.04ubuntu1.3 \
        python3.6-dev=3.6.9-1~18.04ubuntu1.3 \
        python3-pip=9.0.1-2.3~ubuntu1.18.04.4 \
        virtualenv=15.1.0+ds-1.1 \
        git=1:2.17.1-1ubuntu0.7 \
        libssl-dev=1.1.1-1ubuntu2.1~18.04.6 \
        libpq-dev=10.15-0ubuntu0.18.04.1 \
        gfortran=4:7.4.0-1ubuntu2.3 \
        libatlas-base-dev=3.10.3-5 \
        libjpeg-dev=8c-2ubuntu8 \
        libxml2-dev=2.9.4+dfsg1-6.1ubuntu1.3 \
        libxslt1-dev=1.1.29-5ubuntu0.2 \
        zlib1g-dev=1:1.2.11.dfsg-0ubuntu2 \
        ghostscript=9.26~dfsg+0-0ubuntu0.18.04.13 \
        python-celery=4.1.0-2ubuntu1 \
        python-sphinx=1.6.7-1ubuntu1 \
        pkg-config=0.29.1-0ubuntu2 \
        gcc=4:7.4.0-1ubuntu2.3 \
        automake=1:1.15.1-3ubuntu2 \
        libtool=2.4.6-2 \
        openjdk-11-jre-headless=11.0.9.1+1-0ubuntu1~18.04 \
        locales=2.27-3ubuntu1.2 \
        tmux=2.6-3 && \
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