FROM ubuntu:18.04

ARG release_version=v2.4.1
ARG optional_packages

# Silence configuration prompts
ENV DEBIAN_FRONTEND noninteractive

ENV PYTHONUNBUFFERED 1

ENV DJANGO_SETTINGS_MODULE onadata.settings.docker

# Install service dependencies
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
        python3-setuptools \
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
        uwsgi \
        locales && \
    rm -rf /var/lib/apt/lists/*

# Generate and set en_US.UTF-8 locale
RUN locale-gen en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
RUN dpkg-reconfigure locales

# Clone Repository
RUN mkdir -p /srv/onadata
RUN git clone -b ${release_version} https://github.com/onaio/onadata.git /srv/onadata

COPY uwsgi.ini /uwsgi.ini

RUN useradd -m onadata

# Install service requirements
WORKDIR /srv/onadata
RUN python3 -m pip install -U pip && \
    python3 -m pip install --no-cache-dir -r requirements/base.pip

# Install optional requirements
RUN if [ ! -z "$optional_packages"]; then pip install -e ${optional_packages} ; fi

# Compile API Docs
RUN make -C docs html

EXPOSE 8000

CMD ["/usr/local/bin/uwsgi", "--ini", "/uwsgi.ini"]

USER onadata
