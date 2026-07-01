# build.sh — Render.com üçün build script
#!/usr/bin/env bash
set -e

echo "▶ AvtonomCogitate build başladı"
echo "  Python: $(python --version)"
echo "  Pip: $(pip --version)"

# Pip yenilə
pip install --upgrade pip

# Asılılıqları quraşdır
pip install -r requirements.txt

# Qovluqları yarat (mount olunmayacaq halda lazımdır)
mkdir -p memory/backups logs notes

# Verifikasiya: import test
python -c "import config, agent, brain.client, research.searcher, memory.store, security, health_monitor, backup, log_rotation, web.dashboard; print('✓ bütün modullar import olunur')"

echo "▶ Build tamamlandı"
