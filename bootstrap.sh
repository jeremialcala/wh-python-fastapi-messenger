#!/bin/bash
gh repo clone jeremialcala/wh-python-fastapi-messenger
cd wh-python-fastapi-messenger/ || exit
git checkout develop
git pull

docker rm -f wh-python-fastapi-messenger
docker rmi wh-python-fastapi-messenger
docker system prune -a -f
docker build -t wh-python-fastapi-messenger:latest .
docker run --env-file=env_variables -it -p 8080:8080 --name wh-python-fastapi-messenger -d wh-python-fastapi-messenger
