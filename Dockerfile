FROM python:bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y git

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD config/ config/
ADD scripts/ scripts/

RUN python scripts/download_resources.py config/build-config.yml assets artifacts

RUN python scripts/extract_game_info.py assets pre_filter
RUN rm -rf assets

RUN python scripts/filter_game_info.py config pre_filter output output_released
RUN rm -rf pre_filter

RUN python scripts/extract_derived_info.py output output_released
RUN rm -rf output_released

RUN python scripts/zip_all_info.py config/build-config.yml output artifacts
RUN rm -rf output

CMD ["bash"]
