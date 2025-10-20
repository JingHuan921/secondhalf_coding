To test flow: 
## Create virtual environment
cd FYP_secondhalf
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

Go to  langgraph_app and create a `.env` file
Add the following API keys: 
- OPENAI_API_KEY
- MONGODB_URI 

For running backend: 
cd  langgraph_app\src
uvicorn main:app --reload

For running frontend: 
Open a new (powershell) terminal
cd FYP_secondhalf
.\venv\Scripts\activate
cd langgraph_app\src\frontend 
npm run dev
If the terminal shows "'vite' is not recognized as an internal or external command,"
npm install 
[Optional] npm audit fix
npm run dev
