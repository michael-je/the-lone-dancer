FROM fedora:34

WORKDIR /data

# Pre-requisites
RUN dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
RUN dnf install -y ffmpeg python3.8 --nodocs --setopt install_weak_deps=False
RUN dnf clean all

# Environment setup
RUN python3.8 -m venv venv
COPY requirements.txt .
RUN source venv/bin/activate && python3.8 -m pip install -r requirements.txt

# Copy necessary files
COPY *.py .
COPY *.ogg .

# Command to run
CMD source venv/bin/activate && python3.8 bot.py
