import base64
import json
import logging
from pprint import pprint as pr
import os
import time
from youtube_transcript_api import YouTubeTranscriptApi

from claude import Claude
from llm_utils import Prompt, llm_tool, ToolPrompt
from pprint import pprint

api = Claude("anthropic.claude-3-sonnet-20240229-v1:0")

transcript_text = ""


def create_tool_prompt(user_input):
    prompt = ToolPrompt("""
    The input {user_input} contains a link to a video. Give summary or key points from the video. Do not build questions.
    """)
    prompt.set_kwargs(user_input=user_input)
    return prompt



@llm_tool
def get_transcript_from_video_url(video_link: str) -> str:
    """
    Get the transcript of a video from a youtube link.
    """
    video_id = video_link.split("v=")[1].split("&")[0]  # Extract video id from link
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    transcript_text = '\n'.join([x['text'] for x in transcript])
    return transcript_text


video_link = 'https://www.youtube.com/watch?v=vg6-yTRYPjM'
prompt = create_tool_prompt(video_link)
print("prompt:",prompt)
response = prompt.invoke(api, tokens=1024)
print(response["raw_content"])

questions_prompt = Prompt('''User: Prepare a list of only 3 questions based on the transcript below. Give me the output as follows:
                              <questions>
                              - question1
                              - question2
                              ...
                              </questions>

                              <transcript> 
                              {transcript_text}
                              </transcript>

                              Assistant:
                              Sure, here are the 3 questions:
                              ''')
questions_prompt.set_kwargs(transcript_text=transcript_text)
response = questions_prompt.invoke(api, tokens=1024)
print("questions:",response["raw_content"])
questions = response["parsed_objects"]["questions"].split('\n')

for q in questions:
    print(f"Question : {q}")
    user_answer = input("Enter your answer:")
    prompt = Prompt('''Tutor: {q}
                    Student: {user_answer}
                    Tutor: 
    
    ''',
    system_prompt_template='''Check if the answer is correct using the youtube transcript as context. Start by mentioning if the answer is right or wrong. Don't hallucinate.
    <youtube_transcript>
    {context}
    </youtube_transcript>
    '''
    )
    prompt.set_kwargs(user_answer=user_answer, q=q, context=transcript_text)
    result = prompt.invoke(api, tokens=500)

    print(result['raw_content'])

