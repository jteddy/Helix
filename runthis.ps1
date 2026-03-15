# Create directories
mkdir core
mkdir api
mkdir menu
mkdir frontend\static
mkdir patterns

# Move core files
move state.py core\
move makcu_device.py core\
move recoil_loop.py core\

# Move api files
move config.py api\
move patterns.py api\
move status.py api\

# Move games.py to menu
move games.py menu\

# Create empty __init__.py files
echo. > core\__init__.py
echo. > api\__init__.py
echo. > menu\__init__.py
```

After that your structure should look like:
```
Cearum-Web/
├── main.py
├── requirements.txt
├── install.bat / install.sh
├── start.bat / start.sh
├── README.md
├── .gitignore
├── core/
│   ├── __init__.py
│   ├── state.py
│   ├── makcu_device.py
│   └── recoil_loop.py
├── api/
│   ├── __init__.py
│   ├── config.py
│   ├── patterns.py
│   └── status.py
├── menu/
│   ├── __init__.py
│   └── games.py
├── frontend/
│   └── static/        ← index.html goes here later
└── patterns/          ← git ignored, auto-created