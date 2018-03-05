FROM python:3
MAINTAINER Suchan Park <ptncks0121@gmail.com>

EXPOSE 5000

RUN apt-get update -y

RUN mkdir /web
WORKDIR /web

COPY requirements.txt /web/requirements.txt
RUN pip install -r requirements.txt

COPY . /web