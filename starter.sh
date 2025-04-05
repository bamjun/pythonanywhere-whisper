#!/bin/bash

# Django SECRET_KEY 생성
SECRET_KEY=$(uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

# .env 파일이 존재하는지 확인
if [ -f .env ]; then
    # SECRET_KEY가 이미 있는지 확인하고 있으면 업데이트
    if grep -q "^SECRET_KEY=" .env; then
        sed -i "s/^SECRET_KEY=.*$/SECRET_KEY='$SECRET_KEY'/" .env
    else
        echo "SECRET_KEY='$SECRET_KEY'" >> .env
    fi
else
    # .env 파일이 없으면 새로 생성
    echo "SECRET_KEY='$SECRET_KEY'" > .env
    echo "CHECK_DEV_MODE=True" >> .env
    echo "CHECK_LOCAL_MODE=True" >> .env
    echo "ALLOWED_HOSTS=localhost,127.0.0.1" >> .env
fi

echo "SECRET_KEY가 .env 파일에 저장되었습니다."