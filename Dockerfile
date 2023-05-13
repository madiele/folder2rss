# Use the official Python image as the base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the Python script and the config file into the container
COPY folder2rss.py config.json /app/

# Expose the port the server will run on
EXPOSE 8000

# Create a directory to store the podcasts
RUN mkdir /app/podcasts

# Run the Python script when the container starts
CMD ["python3", "folder2rss.py"]

