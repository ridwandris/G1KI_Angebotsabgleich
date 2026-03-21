# Use the official Python image from the Docker Hub, 
# specifically the Alpine version for a smaller image size
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory to /app, which is where our project files will be located
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# Now we copy from the perspective of the project root
COPY pyproject.toml .python-version uv.lock ./

RUN uv sync --locked --no-dev

# Copy all project files (respecting .dockerignore)
COPY . .

# Expose the Streamlit port
EXPOSE 8501

# Start Streamlit
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]