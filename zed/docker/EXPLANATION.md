# Docker Files Explanation for Beginners

## 🐳 What is Docker?

Docker is like a "shipping container" for software. It packages your application and all its dependencies into a container that runs the same way on any computer.

---

## 📄 1. Dockerfile - The Recipe

**Think of it as:** A recipe that tells Docker how to build your custom container image.

### What it does step by step:

```dockerfile
FROM stereolabs/zed:5.1-tools-devel-l4t-r36.4
```
- **Starts with a base image** (like starting with a pre-made cake mix)
- Uses the official ZED SDK image as the foundation

```dockerfile
WORKDIR /home
```
- **Sets the working directory** inside the container
- Like `cd /home` - this is where commands will run

```dockerfile
ENV DEBIAN_FRONTEND=noninteractive
```
- **Sets environment variables**
- Prevents prompts during installation (no "yes/no" questions)

```dockerfile
RUN apt-get update && apt-get install -y ...
```
- **Installs system packages** (like apt install on Ubuntu)
- Installs: build tools, Python, git, editors, etc.
- These packages are **permanently baked into the image**

```dockerfile
RUN pip3 install opencv-python numpy ...
```
- **Installs Python packages**
- These libraries are **permanently baked into the image**
- This is why your pip installs persist!

```dockerfile
COPY entrypoint.sh /entrypoint.sh
```
- **Copies your entrypoint script** into the image
- Makes it executable

```dockerfile
ENTRYPOINT ["/entrypoint.sh"]
```
- **Runs this script automatically** when container starts
- Like an "auto-run" script

### Key Point:
Everything installed with `RUN apt-get install` or `RUN pip install` becomes part of the image. When you build the image once, all these packages are included forever!

---

## 🎼 2. docker-compose.yml - The Orchestra Conductor

**Think of it as:** A configuration file that tells Docker how to run your container with all the right settings.

### What each section does:

```yaml
services:
  zed_env:
```
- Defines a service (container) named "zed_env"

```yaml
    build:
      context: .
      dockerfile: Dockerfile
```
- **Tells Docker to build the image** using your Dockerfile
- If image doesn't exist, it builds it first

```yaml
    runtime: nvidia
```
- **Enables GPU support** (NVIDIA graphics card access)
- Required for ZED camera

```yaml
    privileged: true
```
- **Gives container full access** to host devices
- Needed to access camera hardware directly

```yaml
    network_mode: host
```
- **Uses host's network** directly (no network isolation)
- Container can access localhost, same as your computer

```yaml
    environment:
      - DISPLAY=${DISPLAY}
```
- **Passes environment variables** from your computer to container
- `DISPLAY` is needed for GUI applications (like showing camera feed)

```yaml
    volumes:
      - /dev/:/dev/
      - /tmp/:/tmp/
      - ${HOME}/zed_docker_ai/:/usr/local/zed/resources/
      - ../..:/home
```
- **Mounts directories** from your computer into the container
- Like creating shortcuts/links between host and container
- `/dev/` - access to devices (cameras, USB, etc.)
- `/tmp/` - shared temporary files
- `zed_docker_ai/` - ZED AI resources
- `../..:/home` - your project code (two directories up)

```yaml
    working_dir: /home
```
- **Sets where you start** when you enter the container
- Like `cd /home` automatically

### Key Point:
This file replaces your long `docker run` command! Instead of typing all those flags, you just run `docker compose up`.

---

## 🚪 3. entrypoint.sh - The Startup Script

**Think of it as:** A script that runs automatically when the container starts, like a startup script on your computer.

### What it does:

```bash
set -e
```
- **Stops on errors** - if any command fails, script stops

```bash
git config --global --add safe.directory /home
```
- **Fixes Git permissions** - prevents "dubious ownership" errors
- Needed because files are mounted from host

```bash
if ! grep -q "git-prompt.sh" "$BASHRC"; then
```
- **Checks if Git prompt is already configured**
- Only adds it once (prevents duplicates)

```bash
PS1="🐳 ZED ..."
```
- **Customizes your terminal prompt**
- Shows you're in a Docker container
- Shows current Git branch
- Makes it colorful and informative

```bash
exec bash
```
- **Starts an interactive shell** (bash terminal)
- This is what you see when container starts
- You can type commands here

### Key Point:
This script runs every time the container starts, setting up your environment automatically.

---

## 🔄 How They Work Together

### The Flow:

1. **You run `./build.sh`**
   - Reads `Dockerfile`
   - Builds a custom image with all your packages installed
   - Creates image: `zed:5.1-tools-devel-l4t-r36.4`

2. **You run `./compose_up.sh`**
   - Reads `docker-compose.yml`
   - Starts container with all the settings (GPU, volumes, network, etc.)
   - Container automatically runs `entrypoint.sh`

3. **Container starts**
   - `entrypoint.sh` runs
   - Configures Git, sets up prompt
   - Starts bash shell
   - You're ready to work!

### Why This is Better Than `docker run`:

**Before (docker run):**
```bash
docker run --runtime nvidia -it --privileged -e DISPLAY=$DISPLAY \
  --network host -v /dev/:/dev/ -v /tmp/:/tmp/ ... \
  stereolabs/zed:5.1-tools-devel-l4t-r36.4 sh
```
- Long command, easy to forget
- No custom packages installed
- Have to type it every time

**Now (docker compose):**
```bash
./compose_up.sh
```
- Short command
- All packages already installed (from Dockerfile)
- All settings in one file (docker-compose.yml)
- Automatic setup (entrypoint.sh)

---

## 📝 Summary

| File | Purpose | When It Runs |
|------|---------|--------------|
| **Dockerfile** | Recipe to build image with packages | When you run `./build.sh` |
| **docker-compose.yml** | Settings for running container | When you run `./compose_up.sh` |
| **entrypoint.sh** | Startup script for container | Every time container starts |

---

## 🎯 Key Takeaways

1. **Dockerfile = What's inside** (packages, tools, setup)
2. **docker-compose.yml = How to run** (GPU, volumes, network, etc.)
3. **entrypoint.sh = What happens on startup** (auto-configuration)

All your `apt install` and `pip install` commands in the Dockerfile are **permanently saved** in the image, so you don't need to reinstall them every time!
