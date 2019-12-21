#!/bin/sh
docker run -v $(pwd):/app -p 8123:8123 -p 22022:22 -p 56700:56700/udp -w /app -it hass-dev bash
