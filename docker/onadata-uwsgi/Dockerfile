FROM python:3.9 as intermediate

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

ARG optional_packages

# Download public key for github.com
RUN mkdir -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# Install optional requirements
# Read more on the ssh argument here: https://docs.docker.com/develop/develop-images/build_enhancements/#using-ssh-to-access-private-data-in-builds
# hadolint ignore=DL3013
RUN --mount=type=ssh if [ -n "$optional_packages" ]; then pip install ${optional_packages} ; fi

FROM ubuntu:20.04
COPY --from=intermediate /usr/local/lib/python3.9/site-packages/ /usr/local/lib/python3.9/dist-packages/

ARG release_version=v2.4.1

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
    rm -rf /var/lib/apt/lists/*

# Generate and set en_US.UTF-8 locale
RUN locale-gen en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
RUN dpkg-reconfigure locales

# Create OnaData user and add to tty group
RUN useradd -G tty -m onadata

# Clone Repository and Change owner
RUN mkdir -p /srv/onadata && \
    git clone -b ${release_version} https://github.com/onaio/onadata.git /srv/onadata && \
    chown -R onadata:onadata /srv/onadata

COPY uwsgi.ini /uwsgi.ini
# Install service requirements
WORKDIR /srv/onadata
# hadolint ignore=DL3013
RUN python3.9 -m pip install --no-cache-dir -U pip && \
    python3.9 -m pip install --no-cache-dir -r requirements/base.pip && \
    python3.9 -m pip install --no-cache-dir -r requirements/s3.pip && \
    python3.9 -m pip install --no-cache-dir -r requirements/ses.pip && \
    python3.9 -m pip install --no-cache-dir -r requirements/azure.pip && \
    python3.9 -m pip install --no-cache-dir pyyaml uwsgitop django-prometheus==v2.2.0

# Compile API Docs
RUN make -C docs html

EXPOSE 8000

CMD ["/usr/local/bin/uwsgi", "--ini", "/uwsgi.ini"]

USER onadata
