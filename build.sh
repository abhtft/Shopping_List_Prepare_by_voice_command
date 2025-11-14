#!/bin/bash

echo "Starting build process..."


python -m venv venv
source venv/bin/activate


#for linux
python -m venv venv
source venv/bin/activate


#for windows
python -m venv venv
venv\Scripts\activate
venv\Scripts\deactivate  



# Upgrade pip and install Python dependencies ,need compantibel with python version
pip install --user --upgrade pip #must not in venv mode
pip install --upgrade pip

###should delete and retry pip files from venv
python -m ensurepip --upgrade #install pip from python command
pip install --upgrade pip #if upgrade is required
pip install -r requirements.txt && npm run build && python app.py

python check_requirements.py

#npm used to install the dependencies for the frontend(nodesjs)
npm install
npm run build


if [ ! -d "dist" ]; 
    echo "Error: dist directory not found after build"
    exit 1
fi

if [ ! -f "dist/index.html" ]; then
    echo "Error: index.html not found in dist directory"
    exit 1
fi

echo "Build completed successfully!" 
# Run the server
#python server.py

#npm run build prepares your project for deployment.It runs the TypeScript compiler (tsc) and builds the React application into a static files directory called dist.
#pip installation care