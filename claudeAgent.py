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
from flask import render_template, request, session, flash
from functools import wraps
from auth import login_required


api = Claude("anthropic.claude-3-haiku-20240307-v1:0")



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
    # write transcript to a File
    with open("transcript.txt", "w") as f:
        f.write(transcript_text)
    return transcript_text



def dashboard():
    if request.method == 'POST':
        video_link = request.form['video_link']
        print('video_link',video_link)
        prompt = create_tool_prompt(video_link)
        response = prompt.invoke(api, tokens=1024)
        print('response',response)
        summary = response['raw_content']

        # Get transcript and generate questions
        transcript_text = get_transcript_from_video_url(video_link)
        print('transcript_text',transcript_text)
        questions_prompt = Prompt('''User: Prepare a list of only 3 questions based on the transcript {transcript}. Give me the output as follows:
                                  <questions>
                                  - question1
                                  - question2
                                  ...
                                  </questions>

                                  Assistant:
                                  Sure, here are the 3 questions:
                                  ''')
        questions_prompt.set_kwargs(transcript=transcript_text)
        response = questions_prompt.invoke(api, tokens=1024)
        print('response',response)
        questions = response["parsed_objects"]["questions"].split('\n')
        print('questions',questions)
        print('summary',summary)
        return render_template('quiz.html', summary=summary, questions=questions, video_link=video_link)

    return render_template('dashboard.html')


def submit_quiz():
    answers = request.form
    print('answers',answers)
    video_link = answers['video_link']
    transcript_text = get_transcript_from_video_url(video_link)
    feedback = []

    for q, user_answer in answers.items():
        if q.startswith('question_'):
            prompt = Prompt('''You are asking questions in the form of quiz to the user.
                            Tutor: {q}
                            Me: {user_answer}
                            Tutor: 
            
            ''',
            system_prompt_template='''Check if the answer is correct using the youtube transcript as context. Start by mentioning if the answer is right or wrong. Don't mention the use of transcript. Don't hallucinate.
            <youtube_transcript>
            {context}
            </youtube_transcript>
            '''
            )
            prompt.set_kwargs(user_answer=user_answer, q=q, context=transcript_text)
            result = prompt.invoke(api, tokens=500)
            feedback.append(result['raw_content'])
            print('feedback',feedback)

    return render_template('quiz_results.html', feedback=feedback)