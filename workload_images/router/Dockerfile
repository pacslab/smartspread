FROM python:3
LABEL maintainer="nima.mahmoudi@ualberta.ca"

RUN apt-get update

RUN mkdir /app
COPY ./app /app
COPY ./scripts/init.sh /app/init.sh
RUN chmod 755 /app/init.sh
RUN pip3 install -r /app/requirements.txt

WORKDIR /app/
CMD ["/bin/bash", "/app/init.sh"]
