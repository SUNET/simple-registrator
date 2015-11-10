FROM ubuntu
MAINTAINER Leif Johansson <leifj@sunet.se>
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
RUN apt-get update
RUN apt-get -y install wget python python-dev python-pip git-core
COPY src /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT python registrator.py
