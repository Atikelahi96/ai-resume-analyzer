import os
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from io import BytesIO

# --- LangChain imports ---------------------------------------------------
from langchain_google_genai import ChatGoogleGenerativeAI  # Gemini
from langchain.memory import ConversationBufferMemory
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# --- PDF/Text Parser Imports -------------------------------------------
import PyPDF2  # for handling PDF files
from fastapi.middleware.cors import CORSMiddleware  # for enabling CORS

# 0️⃣ Load keys -----------------------------------------------------------
load_dotenv()  # GOOGLE_API_KEY 

# 1️⃣ Gemini model (tool-use ready) ---------------------------------------
MODEL_ID = "gemini-2.5-pro"  # o
llm = ChatGoogleGenerativeAI(
    model=MODEL_ID,
    temperature=0.7,
    # Removed deprecated parameter 'convert_system_message_to_instructions'
)

# 2️⃣ Short-term memory ---------------------------------------------------
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
)

# 3️⃣ Prompt --------------------------------------------------------------
SYSTEM = """
You are an AI Resume Analyzer.
Your task is to analyze the provided resume and give feedback on how to improve it.
You should also compare the resume with a provided job description and highlight missing keywords.
"""

prompt = ChatPromptTemplate.from_messages([ 
    ("system", SYSTEM),
    MessagesPlaceholder("chat_history", optional=True),
    ("user", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# 4️⃣ Build the agent -----------------------------------------------------
core_agent = create_openai_tools_agent(llm, [], prompt)  # generic helper
agent = AgentExecutor(agent=core_agent, tools=[], memory=memory, verbose=True)

# 5️⃣ FastAPI Integration -------------------------------------------------
app = FastAPI()

# Enable CORS for handling requests from different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Class for handling incoming resume data
class ResumeData(BaseModel):
    job_description: str  # Job description text to compare the resume against

# Route for uploading resume and receiving feedback
@app.post("/analyze_resume")
async def analyze_resume(file: UploadFile = File(...), job_description: str = ""):
    # Check file type and handle accordingly
    if file.filename.endswith(".pdf"):
        file_content = await file.read()
        resume_text = extract_text_from_pdf(BytesIO(file_content))
    elif file.filename.endswith(".txt"):
        resume_text = await file.read()
        resume_text = resume_text.decode("utf-8")
    else:
        return {"error": "Invalid file format. Please upload a PDF or text file."}
    
    # Construct the analysis prompt
    analysis_input = f"Analyze this resume and provide feedback. Resume: {resume_text}"
    if job_description:
        analysis_input += f" Compare with this job description: {job_description}"
    
    # Generate the response
    response = agent.invoke({"input": analysis_input})
    
    return {"response": response["output"]}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
