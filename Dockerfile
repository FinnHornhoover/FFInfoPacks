FROM python:3.13.10-bookworm

WORKDIR /app

ARG FFINFO_FORCED_BUILD=""
ARG FFINFO_SKIP_FILTERING=""
ENV FFINFO_FORCED_BUILD=$FFINFO_FORCED_BUILD
ENV FFINFO_SKIP_FILTERING=$FFINFO_SKIP_FILTERING

RUN apt-get update && apt-get install -y git graphviz graphviz-dev

ADD requirements.txt .
RUN pip install --no-binary pygraphviz -r requirements.txt

ADD config/build-config.yml config/build-config.yml
ADD scripts/download_resources.py scripts/download_resources.py

RUN mkdir -p /root/.ssh && ssh-keyscan -t ed25519 github.com >> /root/.ssh/known_hosts
RUN --mount=type=secret,id=SSH_PRIVATE_KEY \
    --mount=type=secret,id=SSH_PASSPHRASE \
    printf '#!/bin/sh\ncat /run/secrets/SSH_PASSPHRASE\n' > /tmp/ssh-askpass && \
    chmod +x /tmp/ssh-askpass && \
    eval "$(ssh-agent -s)" && \
    { tr -d '\r' < /run/secrets/SSH_PRIVATE_KEY; printf '\n'; } | DISPLAY=:0 SSH_ASKPASS=/tmp/ssh-askpass SSH_ASKPASS_REQUIRE=force ssh-add - && \
    python scripts/download_resources.py config/build-config.yml assets artifacts server_data && \
    rm -f /tmp/ssh-askpass

ADD scripts/extract_game_info.py scripts/extract_game_info.py
RUN python scripts/extract_game_info.py assets pre_filter
RUN rm -rf assets

ADD config/ config/
ADD scripts/filter_game_info.py scripts/filter_game_info.py
RUN python scripts/filter_game_info.py config pre_filter output
RUN rm -rf pre_filter

ADD scripts/extract_derived_info.py scripts/extract_derived_info.py
RUN python scripts/extract_derived_info.py config output server_data
RUN rm -rf server_data

ADD scripts/zip_all_info.py scripts/zip_all_info.py
RUN python scripts/zip_all_info.py config/build-config.yml output artifacts
RUN rm -rf output

CMD ["bash"]
