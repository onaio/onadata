FROM postgres:9.6

RUN apt-get update \
  &&  DEBIAN_FRONTEND=noninteractive \
    apt-get install -y postgresql-9.6-postgis-2.3 \
    postgresql-9.6-postgis-script postgis \
  && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5432

CMD ["postgres"]
