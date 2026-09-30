# Verifier image. Runs in its own container and sees only the paths declared in `artifacts`. It
# rebuilds the agent's crate from the collected sources and runs it twice, so it needs the Rust
# toolchain as well as pytest.

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev ca-certificates \
    # libc6-dev supplies Scrt1.o and crti.o. gcc alone does not pull it under
    # --no-install-recommends, and without it the Rust linker fails on every build.
    && rm -rf /var/lib/apt/lists/*

COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup

# Verifier tooling from a hash-pinned lockfile. Nothing is installed at trial time.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt && rm -f /tmp/requirements.txt

# The rebuild executes agent-authored code inside the image that holds the answer key, so it runs
# as this unprivileged user and never as root.
RUN useradd --create-home --uid 10001 --shell /bin/bash runner

# Warm the toolchain now, while the build still has a network. The agent's own sources arrive
# later as artifacts and overwrite these. Keep in sync with environment/predictor.
COPY skeleton /app/predictor
RUN cd /app/predictor && cargo build --release --offline --locked \
    && cargo clean --release -p claim_predictor \
    && rm -rf /app/predictor/src

# Artifact landing directories must exist before Harbor uploads the declared artifacts.
RUN mkdir -p /app/predictor/src /app/data /app/out

RUN chown -R runner:runner /app && chmod 1755 /app

# The answer keys and the second book. Root-only, and never present in any container the agent
# can reach. /tests is a runtime mount, so permissions set on it here would be ineffective; these
# copies are what the verifier actually reads.
COPY golden /opt/golden
COPY holdout /opt/holdout
RUN chmod 700 /opt/golden /opt/holdout

# Separate mode does not upload tests/ into the image, so the image has to own /tests itself.
# test.sh closes the whole directory to the build user before any agent code runs.
COPY . /tests/

WORKDIR /app
