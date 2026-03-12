FROM python:3.12-slim

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.5

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml poetry.lock* ./

# Install dependencies only (no venv in container, --no-root skips project install)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy source code
COPY src/ src/
COPY tests/ tests/

# Install the project itself now that source is available
RUN poetry install --no-interaction --no-ansi

ENTRYPOINT ["python", "-m", "atlassian_backup"]
