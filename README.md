# AI Mystery Detective Team – The Vanishing Aurora Diamond

A beginner-friendly multi-agent AI mystery detective web application using Gemini + Python + Gradio.

🐳 **Docker Image Available:** [https://hub.docker.com/r/arpit00011/aurora-ai](https://hub.docker.com/r/arpit00011/aurora-ai)

🚀 **Live Demo:** [https://huggingface.co/spaces/Arpit0/aurora-ai](https://huggingface.co/spaces/Arpit0/aurora-ai)

## Local Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Environment Variables:**
   Copy `.env.example` to `.env` and add your Gemini API key.
   ```bash
   cp .env.example .env
   # Edit .env and insert your GEMINI_API_KEY
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```
   Open the application in your browser (typically `http://localhost:7860`).

## Google Cloud Run Deployment

1. **Build the container:**
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-mystery-detective
   ```

2. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy ai-mystery-detective \
     --image gcr.io/YOUR_PROJECT_ID/ai-mystery-detective \
     --platform managed \
     --region YOUR_REGION \
     --allow-unauthenticated \
     --set-env-vars GEMINI_API_KEY="your_api_key_here" \
     --port 7860
   ```