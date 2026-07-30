# Release Operations

## Automatic Flow

A successful `main` CI run derives the next SemVer from Conventional Commits,
creates `chore(release): vX.Y.Z [skip ci]`, tags it, and then:

1. builds and pushes `ghcr.io/<owner>/qmt-mcp:X.Y.Z` and `latest`;
2. updates the persistent `ghcr.io/<owner>/qmt-mcp:buildcache`;
3. optionally mirrors the published digest to a mainland China registry;
4. packages qmtctl for Linux, macOS, and Windows on amd64 and arm64;
5. publishes the six archives and `SHA256SUMS` in one GitHub Release.

The Release job explicitly requests `contents: write`. If repository policy
still blocks the default Actions token, configure a fine-grained
`RELEASE_TOKEN` secret with Contents read/write access to this repository only.
The workflow creates every tag before publishing its Release and deliberately
does not send `target_commitish` to the Releases API. GitHub's built-in Actions
token cannot create a Release when that parameter points to an older commit
whose `.github/workflows/` content differs from the default branch, even with
`contents: write`.

## Build Cache And Layers

The appliance is large because it contains Wine, a Windows Python runtime, and
CJK fonts. The Dockerfile keeps stable work before frequently changing source:

1. pinned Wine base image;
2. Ubuntu runtime packages and fonts;
3. hash-verified Python dependency lock;
4. Wine prefix and Windows Python dependency provisioning (the installer and
   pip download cache are removed inside this layer);
5. launcher scripts and MCP source;
6. short application smoke test.

Changing MCP source therefore reruns only the final copy and smoke steps. PR
and main CI build the complete `linux/amd64` appliance on a native runner and
write the result to the `appliance-ci` GHA cache. Release reads that tested
cache first, then `qmt-mcp:buildcache`, and finally the previous default GHA
cache during migration. It writes a `mode=max` registry cache only for the
highest SemVer tag. Historical release retries may read this cache but cannot
overwrite it. The cache tag is an internal BuildKit artifact, not a runtime
image.

Adding more `RUN` commands does not automatically make the final image larger:
layer contents do. Keep layers separated at dependency invalidation boundaries;
combine cleanup with the command that creates files.

## Mainland China Mirror

Alibaba Cloud ACR Personal Edition is a practical starting point for public
mainland pulls. Tencent TCR and Huawei SWR also speak the same OCI/Docker
registry protocol. Create a public repository first, then configure:

Repository variables:

```text
QMT_MCP_CN_REGISTRY=crpi-xxxx.cn-hangzhou.personal.cr.aliyuncs.com
QMT_MCP_CN_IMAGE=crpi-xxxx.cn-hangzhou.personal.cr.aliyuncs.com/<namespace>/qmt-mcp
```

Repository secrets:

```text
QMT_MCP_CN_USERNAME=<registry login name>
QMT_MCP_CN_PASSWORD=<registry password or scoped credential>
```

All four values must be present or all absent. When configured, the Release
workflow logs in after the GHCR push and copies that exact digest:

```text
<QMT_MCP_CN_IMAGE>:X.Y.Z
<QMT_MCP_CN_IMAGE>:latest
```

It does not build the Dockerfile twice. The mirror path is included in release
notes only after a successful copy.

ACR setup and pull/push syntax:
https://help.aliyun.com/zh/acr/user-guide/use-a-container-registry-personal-edition-instance-to-push-and-pull-images

## Retry An Existing Tag

Use the current workflow implementation to repair an old or partial release:

```bash
gh workflow run release.yml -f release_tag=v0.3.1
gh run watch "$(gh run list --workflow Release --limit 1 --json databaseId --jq '.[0].databaseId')"
```

The workflow verifies that the tag exists and that its `VERSION` matches before
rebuilding or overwriting assets. Retrying an older tag never moves `latest`
backward. Leaving `release_tag` blank releases current `main`; automatic main
releases remain the normal path.
