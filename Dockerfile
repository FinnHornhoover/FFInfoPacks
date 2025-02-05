FROM python:bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y git graphviz graphviz-dev

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD config/build-config.yml config/build-config.yml
ADD scripts/download_resources.py scripts/download_resources.py
RUN python scripts/download_resources.py config/build-config.yml assets artifacts server_data

ADD scripts/extract_game_info.py scripts/extract_game_info.py
RUN python scripts/extract_game_info.py assets pre_filter
RUN rm -rf assets

ADD config/ config/
ADD scripts/filter_game_info.py scripts/filter_game_info.py
RUN python scripts/filter_game_info.py config pre_filter output
RUN rm -rf pre_filter

ADD scripts/extract_derived_info.py scripts/extract_derived_info.py
RUN python scripts/extract_derived_info.py config/build-config.yml output server_data
RUN rm -rf server_data

ADD scripts/zip_all_info.py scripts/zip_all_info.py
RUN python scripts/zip_all_info.py config/build-config.yml output artifacts
RUN rm -rf output

CMD ["bash"]
