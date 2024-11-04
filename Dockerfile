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
RUN python scripts/filter_game_info.py config pre_filter output_all output_released
RUN rm -rf pre_filter
RUN python scripts/extract_derived_info.py output_all
RUN python scripts/extract_derived_info.py output_released

RUN mkdir -p artifacts
RUN cd output_all && for i in */; do zip -r "../artifacts/${i%/}_all.zip" "$i"; done
RUN cd output_released && for i in */; do zip -r "../artifacts/${i%/}_released.zip" "$i"; done
RUN rm -rf output_all output_released

CMD ["bash"]
