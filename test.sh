#!/usr/bin/env bash

host=http://localhost:5000

# Carl.
curl -X POST -F 'name=Carl' "$host/candidate/"
args=()
for time in 2018-10-{15..19}T09 2018-10-17T{10..11}; do
    args+=(-F "time=$time")
done
curl -X PUT "${args[@]}" "$host/candidate/1"

# Sarah.
curl -X POST -F 'name=Sarah' "$host/interviewer/"
args=()
for time in 2018-10-{15,17}T{12..17} 2018-10-{16,18}T{09..11}; do
    args+=(-F "time=$time")
done
curl -X PUT "${args[@]}" "$host/interviewer/2"

# Philipp.
curl -X POST -F 'name=Philipp' "$host/interviewer/"
args=()
for time in 2018-10-{15..19}T{09..15}; do
    args+=(-F "time=$time")
done
curl -X PUT "${args[@]}" "$host/interviewer/3"

# Now get the overlap.
curl 'http://localhost:5000/interview?id=1&id=2&id=3'
