FROM ghcr.io/linuxserver/baseimage-alpine:3.17
# using linuxserver base alpine image, to get nice things like ability to set timezone with environmen variables and run container as specifid uid.

# Install python3-pip and dependencies.
RUN apk add --no-cache py3-pip ffmpeg git cronie openrc busybox-openrc curl

# Install package from pip.
RUN pip install pasjonsfrukt

# Create yield directory, /app directory is already created with base image.
RUN mkdir /app/yield

# Set workdir for app
WORKDIR /app

# Expose port
EXPOSE 8000

# Create healthcheck. Commented out, because not a lot of people use them.
#HEALTHCHECK CMD curl http://127.0.0.1:8000 || exit 1

# Run app. Forwarding headers to work nice with reverse proxies.
ENTRYPOINT ["pasjonsfrukt", "serve", "--forwarded-allow-ips='*'", "--proxy-headers", "--host", "0.0.0.0" ]
