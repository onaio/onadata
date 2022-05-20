FROM postgres:9.6

RUN apt-get update \
  &&  DEBIAN_FRONTEND=noninteractive \
    apt-get install --no-install-recommends -y \
      postgresql-9.6-postgis-2.3=2.3.1+dfsg-2+deb9u2 \
      postgresql-9.6-postgis-2.3-scripts=2.3.1+dfsg-2+deb9u2 \
      postgis=2.3.1+dfsg-2+deb9u2 \
  && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5432

CMD ["postgres"]
