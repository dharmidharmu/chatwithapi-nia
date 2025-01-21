python -m venv customgptapp2
source customgptapp2/bin/activate
python -m pip install --upgrade pip
echo "Installing Requirements"
pip install -r requirements.txt
echo "Installing uvicorn separately"
pip install fastapi uvicorn python-multipart
echo "The uvicorn version installed is:"
uvicorn --version
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind=0.0.0.0:8000
echo "Startup Completed"