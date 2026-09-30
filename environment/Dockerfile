# Agent environment. The task is a Rust binary with no dependencies, so this carries the
# toolchain, the export and the project stub and nothing else. tests/ and solution/ are never
# copied here.

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

# tmux and asciinema are required by the agent runtime and cannot be fetched at run time, so they
# are installed here regardless of the network setting.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY data/ /app/data/
COPY predictor/ /app/predictor/

# Warm the toolchain so the agent's first build is its own code only. The crate has no
# dependencies, so this is the stub compiling against the standard library.
RUN cd /app/predictor && cargo build --release --offline --locked \
    && rm -rf /app/predictor/target/release/incremental

RUN mkdir -p /app/out

CMD ["/bin/bash"]
