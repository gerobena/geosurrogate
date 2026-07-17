# Deploying the public demo to a HuggingFace Space

> **Note (2026):** HuggingFace now requires a **paid PRO plan** to create Docker
> (and Gradio) Spaces — only Static Spaces stay free, and those cannot run this
> app. The free, no-account way to let anyone try the demo is the one-command
> Docker run documented in the main README (the GHCR image is public). Keep this
> file as a reference for standing up a hosted Space if you later take PRO or
> move to another container host (e.g. Google Cloud Run, which runs the same
> public image and scales to zero).

The Space reuses the image published to GHCR by the `Docker image` workflow, so
there is nothing to compile here. These are the one-time steps to stand it up.
Steps 1–3 need your GitHub/HuggingFace accounts, so they are yours to do; the
two files in this folder (`Dockerfile`, `README.md`) are what the Space runs.

## 1. Make the GHCR image public

HuggingFace's builder pulls the base image anonymously, so it must be public:

- GitHub → your avatar → **Your packages** → **geosurrogate**
- **Package settings** → Danger Zone → **Change visibility** → **Public**

(This exposes only the built demo image — not your code visibility, which the
repo controls separately.)

## 2. Create the Space

- huggingface.co → **New Space**
- Owner: your account · Space name: `geosurrogate` (or `geosurrogate-demo`)
- License: **MIT** · SDK: **Docker** → **Blank** template
- Visibility: **Public** → **Create Space**

## 3. Put these two files in the Space

The Space is its own git repo. Either use the web UI (**Files → Add file →
Create new file**) to create `README.md` and `Dockerfile` with the contents from
this folder, or push with git:

```bash
git clone https://huggingface.co/spaces/<your-user>/geosurrogate
cd geosurrogate
cp /path/to/geosurrogate/deploy/hf-space/README.md .
cp /path/to/geosurrogate/deploy/hf-space/Dockerfile .
git add README.md Dockerfile
git commit -m "geosurrogate demo Space"
git push
```

When git asks for a password, use a **HuggingFace access token** with *write*
scope (huggingface.co → Settings → Access Tokens), not your account password.

## 4. Watch it build

The Space rebuilds automatically on every push. Follow the **Logs** tab; when the
status turns **Running**, the public URL serves the dashboard.

## Updating later

When the GHCR image changes (a new push to `main` rebuilds `:latest`), trigger a
Space rebuild: Space → **Settings** → **Factory rebuild** (it re-pulls the base
image). Nothing in this folder needs to change for a content update.
