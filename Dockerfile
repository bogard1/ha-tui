FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ha_client.py widgets.py ha-tui.py ./

# Required for the TUI to render correctly in a terminal
ENV TERM=xterm-256color
ENV PYTHONUNBUFFERED=1

# Mount your dashboard.yml and .env at runtime:
#   docker run -it \
#     -v $(pwd)/dashboard.yml:/app/dashboard.yml \
#     -v $(pwd)/.env:/app/.env \
#     ha-tui
ENTRYPOINT ["python", "ha-tui.py"]
