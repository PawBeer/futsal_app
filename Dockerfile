FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js (needed to build Tailwind CSS)
RUN apt-get update && apt-get install -y curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm

# Copy project files
COPY . .

# Install Node dependencies
RUN npm install

# Build production CSS
RUN npm run build:css

# Run Gunicorn
CMD ["gunicorn", "futsal_app.wsgi:application", "--bind", "0.0.0.0:8000"]

