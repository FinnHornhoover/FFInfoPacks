FROM python:3.13.10-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y git graphviz graphviz-dev

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD config/build-config.yml config/build-config.yml
ADD scripts/download_resources.py scripts/download_resources.py

RUN mkdir -p ~/.ssh
RUN ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
RUN --mount=type=secret,id=SSH_PASSPHRASE echo "echo $(cat /run/secrets/SSH_PASSPHRASE)" > ~/.ssh_askpass && chmod +x ~/.ssh_askpass
RUN --mount=type=secret,id=SSH_PRIVATE_KEY eval $(ssh-agent -s) && \
    echo "$(cat /run/secrets/SSH_PRIVATE_KEY)" | tr -d '\r' | DISPLAY=None SSH_ASKPASS=~/.ssh_askpass ssh-add - && \
    python scripts/download_resources.py config/build-config.yml assets artifacts server_data

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
