import os
import json
import logging
import boto3
import pandas as pd
import base64
from botocore.exceptions import ClientError
from PyPDF2 import PdfReader
import docx
from PIL import Image
import pytesseract
import gradio as gr
from markdownify import markdownify as md

from claude import Claude3Wrapper
from claude_image import Claude3ImageWrapper

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.txt', '.md', '.csv']:
        with open(file_path, 'r') as f:
            return f.read()
    elif ext == '.pdf':
        pdf_reader = PdfReader(file_path)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    elif ext == '.docx':
        doc = docx.Document(file_path)
        text = '\n'.join([para.text for para in doc.paragraphs])
        return text
    elif ext in ['.html', '.htm']:
        with open(file_path, 'r') as f:
            html_content = f.read()
            return md(html_content)
    elif ext in ['.png', '.jpg', '.jpeg']:
        with open(file_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
        return image_data
    else:
        return 'Unsupported file format'

def process_files(files, question):
    if not files or not question:
        return "Please upload files and enter a question.", None

    combined_text = ''
    image_data = None
    for file in files:
        filename = file.name
        print("filename", filename)
        file_path = filename
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_data = extract_text_from_file(file_path)
        else:
            combined_text += '<fileContent>\n' + extract_text_from_file(file_path) + '<fileContent>\n'

    prompt = (
        f"Use the file contents provided in the <fileContent> tag to answer the question provided in the <userQuestion> tag:\n\n",
        f"<userQuestion>",
        question,
        f"</userQuestion>\n\n",
        combined_text
    )
    prompt = "".join(prompt)
    print(prompt)
    
    if image_data:
        wrapper = Claude3ImageWrapper("anthropic.claude-3-haiku-20240307-v1:0")
        response = wrapper.invoke(prompt, image_data,"output.txt")
    else:
        wrapper = Claude3Wrapper("anthropic.claude-3-sonnet-20240229-v1:0")
        response = wrapper.invoke(prompt, "output.txt")

    return response["content"], "output.txt"

with gr.Blocks(css="""
    body { font-family: Arial, sans-serif; background-color: #f7f7f7; color: #333; }
    .gradio-container { max-width: 800px; margin: auto; padding: 20px; border-radius: 10px; background-color: #fff; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    h2 { font-size: 40px; font-weight: bold; margin-bottom: 20px; }
    .gradio-row { margin-bottom: 20px; }
    .gradio-file, .gradio-textbox, .gradio-button { width: 100%; }
    .gradio-textbox textarea { font-size: 18px; padding: 10px; border-radius: 5px; border: 1px solid #ccc; }
    .gradio-button { font-size: 18px; padding: 10px 20px; border: none; border-radius: 5px; background-color: #4CAF50; color: white; cursor: pointer; }
    .gradio-button:hover { background-color: #45a049; }
""") as demo:
    gr.Markdown("## Upload Files and Ask a Question")
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Upload Files", file_count="multiple")
            question_input = gr.Textbox(label="Question")
        with gr.Column():
            response_output = gr.Textbox(label="Response", lines=10)
            download_button = gr.File(label="Download Response")

    submit_button = gr.Button("Submit")

    submit_button.click(
        process_files,
        inputs=[file_input, question_input],
        outputs=[response_output, download_button]
    )

demo.launch(share=False)
