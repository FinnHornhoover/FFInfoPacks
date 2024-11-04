FROM python:bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y git zip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config/ config/
COPY scripts/ scripts/

RUN python scripts/download_resources.py config/build-config.yml

RUN python scripts/extract_game_info.py assets pre_filter
RUN rm -rf assets

RUN python scripts/filter_game_info.py config pre_filter output output_released
RUN rm -rf pre_filter

RUN python scripts/extract_derived_info.py output output/info
RUN python scripts/extract_derived_info.py output_released output/info_released
RUN rm -rf output_released

RUN mkdir -p artifacts
RUN cd output && for i in */; do zip -rq "../artifacts/${i%/}.zip" "$i"; done
RUN rm -rf output

CMD ["bash"]
