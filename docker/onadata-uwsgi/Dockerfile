FROM python:3.10-alpine3.17 as intermediate
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

ARG optional_packages

# Download public key for github.com
RUN apk add -qU openssh git
RUN mkdir -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# Install optional requirements
# Read more on the ssh argument here: https://docs.docker.com/develop/develop-images/build_enhancements/#using-ssh-to-access-private-data-in-builds
# hadolint ignore=DL3013
RUN --mount=type=ssh if [ -n "$optional_packages" ]; then pip install ${optional_packages} ; fi

FROM python:3.10-alpine3.17
COPY --from=intermediate /usr/local/lib/python3.10/site-packages/ /home/onadata/.local/lib/python3.10/site-packages/

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE onadata.preset.docker

ARG optional_packages
ARG release_version=v3.8.3

# Create container user
RUN addgroup -g 11211 onadata
RUN adduser -D -u 1121 -G onadata onadata

# Install dependencies
RUN apk add --no-cache --virtual .build-deps\
        bash\
        binutils\
        proj-dev\
        memcached\
        libmemcached-dev\
        supervisor\
        git\
        openssl-dev\
        libpq-dev\
        gfortran\
        openblas-dev\
        linux-headers\
        jpeg-dev\
        libxml2-dev\
        libxslt-dev\
        zlib-dev\
        ghostscript\
        py3-sphinx\
        pkgconfig\
        gcc\
        automake\
        libtool\
        openjdk11-jre-headless\
        build-base\
        musl\
        musl-utils\
        musl-locales\
        tzdata\
        netcat-openbsd\
        gdal\
        geos\
        geos-dev\
        gdal-dev

# Set Locale Info
RUN echo "export LC_ALL=en_US.UTF-8" >> /etc/profile.d/locale.sh

# Install OnaData
RUN mkdir -p /srv/onadata

RUN git clone -b ${release_version} https://github.com/onaio/onadata.git /srv/onadata
RUN chown -R onadata:onadata /home/onadata
RUN chown -R onadata:onadata /srv/onadata

WORKDIR /srv/onadata
USER onadata

RUN pip install --no-cache-dir -r requirements/base.pip
RUN pip install --no-cache-dir -r requirements/s3.pip
RUN pip install --no-cache-dir -r requirements/ses.pip
RUN pip install --no-cache-dir -r requirements/azure.pip
RUN pip install --no-cache-dir setuptools==65.5.1 PyYAML==6.0 uwsgitop==0.11

# Generate documentation
RUN make -C docs html

CMD ["/home/onadata/.local/bin/uwsgi", "--ini", "/uwsgi.ini"]
