FROM python:3.5
RUN apt-get install curl
RUN mkdir /source
WORKDIR /source
COPY requirements.txt /source
RUN pip install -r requirements.txt
RUN curl -O https://raw.githubusercontent.com/WildApricot/ApiSamples/master/python/WaApi.py
CMD python controller.py