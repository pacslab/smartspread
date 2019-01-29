FROM debian:latest
LABEL maintainer="nima.mahmoudi@ualberta.ca"

ENV HOSTNAME=unknown
# runmode can be anything, it will added as postfix. na will be discarded.
ENV postfix=n/a

RUN apt-get update

RUN apt-get -y install sysbench \
    python3 python3-pip

RUN mkdir /code
COPY ./sysbench-app /code
COPY ./rmqserver /code/rmqserver
COPY ./scripts/init.sh /code/init.sh
RUN chmod 755 /code/init.sh
RUN chmod 755 /code/lin.sh
RUN pip3 install -r /code/rmqserver/requirements.txt
RUN pip3 install -r /code/requirements.txt

WORKDIR /code/
CMD /bin/sh /code/init.sh ${HOSTNAME} ${postfix}
