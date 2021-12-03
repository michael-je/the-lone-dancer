FROM fedora:34

WORKDIR /data

# Pre-requisites
RUN dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
RUN dnf install -y ffmpeg python3.9 --nodocs --setopt install_weak_deps=False && dnf clean all

# Environment setup
COPY requirements.txt .
RUN python3.9 -m ensurepip && python3.9 -m pip install --no-deps -r requirements.txt

# Copy necessary files
COPY ["*.py", "*.ogg", "./"]
COPY tests/*.py tests/
COPY pafy_fixed/*.py pafy_fixed/

# Command to run
CMD python3.9 bot.py
