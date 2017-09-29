FROM python:3.6
RUN apt-get install git
RUN mkdir /source
WORKDIR /source
COPY requirements.txt /source
RUN pip install -r requirements.txt
ENV PYTHONPATH=/source
CMD /usr/local/bin/python scripts/rfidreader