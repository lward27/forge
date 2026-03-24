FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --user

COPY src/setup.py .
COPY src/forge_platform ./forge_platform
RUN pip install . --user

RUN opentelemetry-bootstrap -a install

EXPOSE 8000

ENTRYPOINT ["opentelemetry-instrument", "python", "-m", "forge_platform"]
