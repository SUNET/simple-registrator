FROM debian

MAINTAINER Leif Johansson <leifj@sunet.se>

RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
RUN apt-get update && apt-get -y dist-upgrade && apt-get -y install wget python python-dev python-pip git-core && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN cd /app && python setup.py install

ENTRYPOINT ["/usr/local/bin/registrator"]
