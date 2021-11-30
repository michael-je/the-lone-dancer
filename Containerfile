FROM fedora:34

WORKDIR /data

# Pre-requisites
RUN dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
RUN dnf install -y ffmpeg python3.8 --nodocs --setopt install_weak_deps=False
RUN python3.8 -m ensurepip
RUN dnf clean all

# Environment setup
COPY requirements.txt .
RUN python3.8 -m pip install -r requirements.txt

# Copy necessary files
COPY *.py .
COPY *.ogg .

# Command to run
CMD python3.8 bot.py
