# QUIRKS — Known Challenges in air-gap-deploy-kit

> **All data is synthetic.** All image names, digests, and package versions in samples
> and tests are fabricated. No real registry credentials or production infrastructure
> is used anywhere in this project.

---

## 1. Docker Image Digest vs Tag Staleness

`bundle_images()` records the image digest at bundle time using `docker inspect --format={{.Id}}`.

At deploy time, `load_docker_images()` checks whether the local image digest matches
before loading the tar. If someone re-tagged the same image name locally with different
content, the digest check will catch it and force a reload from the bundle tar.

**Gotcha:** `docker inspect --format={{.Id}}` returns the image ID (a content hash), not
the registry manifest digest. These are different things. The image ID changes when the
image is rebuilt locally; the registry digest changes when the image is pushed with new
layers. This tool tracks image ID, not registry digest, because registry digests require
network access — which defeats the point of an air-gap kit.

---

## 2. pip download --only-binary Limitation

`wheel_bundler.py` passes `--only-binary=:all:` to `pip download` to avoid downloading
source distributions that require compilation on the target. If a package has no binary
wheel for the target platform, `pip download` will fail.

Workaround: run `kit bundle` on a machine with the same OS/arch as the target. For
cross-platform bundles, build wheels manually and place them in `bundle/wheels/` before
running `kit manifest`.

---

## 3. Ollama Model Export Is Disabled

Copying Ollama blobs alone does not recreate a usable model because model manifests are
also required. `kit bundle --models ...` therefore fails clearly instead of shipping an
archive the target cannot restore. A future implementation must export and restore both
manifests and their exact referenced blobs.

---

## 4. Wheel Checksum Is Post-Download

`download_wheels()` records SHA-256 checksums after `pip download` writes the files.
This means the manifest captures what was actually downloaded, not what was requested.
If pip silently swaps a wheel for a compatible alternative (e.g., a pure-python fallback
for a platform-specific package), the manifest will record the actual wheel, not the
requested one.

---

## 5. Verifier Ollama Model Matching Is Prefix-Based

`check_ollama()` matches the requested model name by prefix:

```python
matched = [p for p in pulled if p.startswith(model.split(":")[0])]
```

This means `--ollama-model gemma` matches multiple Gemma-family tags. Requesting
`gemma3:4b` may also match another `gemma3` tag if that is what is pulled.

This is intentionally permissive — the exact tag varies across Ollama versions, and the
bench cares that a gemma family model is available, not the precise quantization level.

---

## 6. No Windows Docker Path Support

`save_image()` passes `str(output_path)` directly to `docker save -o`. On Windows with
Docker Desktop, paths containing backslashes may need forward-slash normalization or
quoting. The current implementation works on Linux/macOS and WSL2 but has not been
tested on native Windows Docker.

---

## 7. Air-Gap Transfer Not Automated

This kit bundles and deploys but does not handle the physical transfer step. Getting
`kit-bundle/` from the internet-connected build machine to the air-gapped target is
out of scope — use USB, internal file transfer, or a data diode as appropriate for
your security posture.

---

## 8. verify --acme-url Assumes Docker is Running

`check_acme_api()` makes an HTTP request to acme-parts-cloud. The service must already
be started before running `kit verify`. The kit does not start Docker containers — that
remains a manual step or is handled by your orchestrator (Docker Compose, systemd, etc.).

A future version may add `kit start` and `kit stop` commands wrapping `docker compose`.

---

## 9. Rehearsal Never Pulls Images

`kit rehearse` starts its container with both `--pull=never` and `--network none`.
The selected image must already be present on the rehearsal host. This makes a missing
prerequisite fail visibly instead of silently using the network.

Integrity checks fail closed before wheel installation or smoke commands. Docker image
tars are not loaded during the default rehearsal because that mutates the host daemon.
Passing `--load-docker` opts into that mutation and adds a post-load image-ID check.
Container cleanup failure is itself a failed rehearsal step.
