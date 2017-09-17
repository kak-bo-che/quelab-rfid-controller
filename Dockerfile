FROM python:3.5
RUN mkdir /source
WORKDIR /source
COPY requirements.txt /source
RUN pip install -r requirements.txt
CMD python controller.py