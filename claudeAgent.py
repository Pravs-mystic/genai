import base64
import json
import logging
from pprint import pprint as pr
import os
import time
from youtube_transcript_api import YouTubeTranscriptApi, VideoUnavailable, TranscriptsDisabled, NoTranscriptFound
from claude import Claude
from llm_utils import Prompt, llm_tool, ToolPrompt
from pprint import pprint
from flask import render_template, request, session, flash,redirect, url_for
from functools import wraps
from auth import login_required
from ollama_client import OllamaClient
from botocore.exceptions import ClientError
import requests
from urllib.parse import urlparse, parse_qs
import re

api = Claude("anthropic.claude-3-haiku-20240307-v1:0")
# api = OllamaClient("llama3.1")



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
    try:
        # Extract video id from link
        parsed_url = urlparse(video_link)
        video_id = parse_qs(parsed_url.query).get('v', [None])[0]
        
        if not video_id:
            raise ValueError("Invalid YouTube URL. Unable to extract video ID.")

        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        print('transcript', transcript)
        transcript_text = '\n'.join([x['text'] for x in transcript])
        
        # write transcript to a File
        try:
            with open("transcript.txt", "w", encoding='utf-8') as f:
                f.write(transcript_text)
        except IOError as e:
            print(f"Warning: Unable to write transcript to file: {str(e)}")
        
        return transcript_text

    except ValueError as e:
        raise ValueError(f"Error with video URL: {str(e)}")
    except VideoUnavailable:
        raise ValueError("The video is unavailable. It might be private or deleted.")
    except TranscriptsDisabled:
        raise ValueError("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("No transcript found for this video. It might not have closed captions.")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred while fetching the transcript: {str(e)}")

def dashboard():
    if request.method == 'POST':
        video_link = request.form['video_link']
        print('video_link', video_link)
        
        try:
            # First, try to get the transcript
            transcript_text = get_transcript_from_video_url(video_link)
            print('transcript_text', transcript_text)
        except ValueError as e:
            # If there's an error getting the transcript, flash the error and return to dashboard
            flash(f"Error: {str(e)}", 'error')
            return render_template('dashboard.html')
        except (VideoUnavailable, TranscriptsDisabled, NoTranscriptFound) as e:
            # Handle specific YouTube transcript API errors
            flash(f"Error: {str(e)}", 'error')
            return render_template('dashboard.html')
        except Exception as e:
            # Handle any other unexpected errors
            flash(f"An unexpected error occurred: {str(e)}", 'error')
            return render_template('dashboard.html')
        
        # If we successfully got the transcript, proceed with API calls
        try:
            prompt = create_tool_prompt(video_link)
            response = prompt.invoke(api, tokens=1024)
            print('response', response)
            raw_content = response['raw_content']
            
            # Extract summary content after tool_invoke tags
            summary_match = re.search(r'</tool_invoke>\s*(.*)', raw_content, re.DOTALL)
            if summary_match:
                summary = summary_match.group(1).strip()
            else:
                summary = raw_content  # Fallback to full content if no match
            print('summary', summary)

            # Generate questions
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
            questions = response["parsed_objects"]["questions"].split('\n')

            return render_template('quiz.html', summary=summary, questions=questions, video_link=video_link)

        except ClientError as e:
            flash(f"An error occurred with the Claude API: {e.response['Error']['Message']}", 'error')
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", 'error')
        
        # If any error occurred after getting the transcript, redirect back to the dashboard
        return render_template('dashboard.html')

    return render_template('dashboard.html')

def submit_quiz():
    try:
        answers = request.form
        print('answers', answers)
        video_link = answers.get('video_link')
        
        if not video_link:
            flash("Video link is missing. Please try again.", 'error')
            return redirect(url_for('dashboard'))

        try:
            transcript_text = get_transcript_from_video_url(video_link)
        except Exception as e:
            flash(f"Error fetching video transcript: {str(e)}", 'error')
            return redirect(url_for('dashboard'))

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
                
                try:
                    result = prompt.invoke(api, tokens=500)
                    feedback.append(result['raw_content'])
                except ClientError as e:
                    feedback.append(f"Error processing answer: {e.response['Error']['Message']}")
                except Exception as e:
                    feedback.append(f"Unexpected error processing answer: {str(e)}")
                
                print('feedback', feedback)

        if not feedback:
            flash("No answers were processed. Please try again.", 'warning')
            return redirect(url_for('dashboard'))

        return render_template('quiz_results.html', feedback=feedback)

    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('dashboard'))