FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Docker always uses the Anthropic API — claude CLI is not available inside the container
ENV USE_API=true

CMD ["python", "bot/telegram_bot.py"]
