# Proposed Fix for #5742

Based on the issue description, this is a knowledge/documentation bounty task to answer two specific unanswered questions (#5654 and #5662) regarding Docker multi-image/multi-platform save archive validation in the context of the repository's support channels or Q&A knowledge base.

### Implementation Plan

1. **Answer Question #5654**: Explain how to validate a multi-image Docker save archive (`docker save`) for exact image IDs and tags without fully loading it, typically by inspecting the `manifest.json` and config JSON files inside the tarball.
2. **Answer Question #5662**: Explain how to validate a Docker 29 / containerd-backed multi-platform save archive (which uses OCI image layout structure rather than the legacy Docker format) by inspecting `index.json`, the OCI manifest list, and content addressable blobs.
3. **Commit Answers**: Add the resolutions to the repository's knowledge base, FAQ, or issue resolution documentation as appropriate.

---

### Code Patch

Since this is a documentation/bounty task addressing retrieval failures in the Q&A knowledge base, here is the Markdown patch documenting the answers for inclusion in the repository's knowledge base or FAQ.

```markdown
# Knowledge Base: Docker Archive Validation Answers

## Q: How can a multi-image Docker save archive be validated for exact image IDs and tags?

**Answer:**
A legacy Docker save archive (created via `docker save`) is a uncompressed tarball containing a root `manifest.json` file alongside individual image layer directories. You can validate the exact image IDs and tags without loading the archive into a Docker daemon by inspecting the archive structure programmatically:

1. **Extract/Inspect `manifest.json`**:
   The root `manifest.json` maps each tag to its respective repository path and layer files:
   ```json
   [
     {
       "Config": "sha256:<config_id>.json",
       "RepoTags": ["my-image:latest"],
       "Layers": [
         "sha256:<layer_id>/layer.tar",
         ...
       ]
     }
   ]
   ```
2. **Verify Image IDs**:
   The `<config_id>.json` file corresponding to the configuration blob inside the tarball contains the canonical image ID (which matches the sha256 checksum of the config file itself). You can compute the SHA256 hash of the extracted config JSON to verify the exact image ID.

---

## Q: How should a Docker 29 containerd multi-platform save archive be validated when using OCI layout?

**Answer:**
Docker 29 and modern containerd-backed image exports often use the OCI Image Layout specification rather than the legacy Docker tar format. Validation requires checking the OCI layout components:

1. **Verify `oci-layout` file**:
   Ensure the root contains an `oci-layout` file with:
   ```json
   {"imageLayoutVersion": "1.0.0"}
   ```
2. **Inspect `index.json`**:
   The root `index.json` lists the manifests included in the archive (frequently a multi-platform index/manifest list):
   ```json
   {
     "schemaVersion": 2,
     "manifests": [
       {
         "mediaType": "application/vnd.oci.image.manifest.v1+json",
         "digest": "sha256:<manifest_digest>",
         "size": 1234,
         "platform": {
           "architecture": "amd64",
           "os": "linux"
         }
       }
     ]
   }
   ```
3. **Validate Blobs**:
   Navigate to `blobs/sha256/<digest>` for each referenced manifest and config to ensure all platform-specific layers exist and their content-addressable checksums match their file names.
```
