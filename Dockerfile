FROM ubuntu:latest
LABEL authors="egorteplonogov"

ENTRYPOINT ["top", "-b"]