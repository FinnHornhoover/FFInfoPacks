#!/bin/bash
mkdir -p artifacts
cd output
for i in */; do
    nickname=$(yq ".config.${i%/}.nickname // \"unnamed\"" "../config/build-config.yml")
    revision=$(yq ".config.${i%/}.revision" "../config/build-config.yml")
    zip -rq "../artifacts/${nickname}_${i%/}_r${revision}.zip" "$i"
done
