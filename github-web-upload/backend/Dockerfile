FROM python:3.12-slim

WORKDIR /app

# CloudBase uploads this image to TCR. Use the lightweight production dependency
# set so the image stays small and reliable to upload.
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY . .

EXPOSE 80

# CloudRun injects PORT. The launcher also creates/migrates the MySQL schema.
CMD ["python", "scripts/start_cloudrun.py"]
