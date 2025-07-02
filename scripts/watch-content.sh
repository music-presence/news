#!/bin/bash

ID=$1
[[ -z "$1" ]] && echo "Pass a news ID" && exit 1;

cd $(realpath "$(dirname "$0")/..")

while sleep 1; do
    NEW=$(stat -c %Y "news/$ID/content.md");
    [[ "$NEW" != "$OLD" ]] && \
        inv translations && \
        inv resize-banners && \
        LOCALHOST=1 inv dist;
    OLD=$NEW;
done
