# Create directories
New-Item -ItemType Directory -Force -Path core
New-Item -ItemType Directory -Force -Path api
New-Item -ItemType Directory -Force -Path menu
New-Item -ItemType Directory -Force -Path frontend\static
New-Item -ItemType Directory -Force -Path patterns

# Move core files
Move-Item -Force state.py         core\state.py
Move-Item -Force makcu_device.py  core\makcu_device.py
Move-Item -Force recoil_loop.py   core\recoil_loop.py

# Move api files
Move-Item -Force config.py        api\config.py
Move-Item -Force patterns.py      api\patterns.py
Move-Item -Force status.py        api\status.py

# Move games.py to menu
Move-Item -Force games.py         menu\games.py

# Create empty __init__.py files
"" | Out-File -Encoding utf8 core\__init__.py
"" | Out-File -Encoding utf8 api\__init__.py
"" | Out-File -Encoding utf8 menu\__init__.py

Write-Host "Done. Directory structure created."
