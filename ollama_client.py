import os
import json
from datetime import datetime as dt
from ollama import Client
from claude import Claude


class OllamaClient:
    def __init__(self, model):
        self.model = model
        self.client = Client(host="http://10.0.0.9:11434")
        self.claude = Claude("anthropic.claude-3-haiku-20240307-v1:0")

    def invoke_chat(self, messages, system="", tokens=1024):
        if system:
            messages = [{"role": "system", "content": system}] + messages
        response = self.client.chat(
            model=self.model, messages=messages, options={"num_ctx": tokens}
        )

        total_duration = int(response["total_duration"]) / 1000000000
        debug_info = (
            f"\n**Done Reason**: {response['done_reason']}"
            f"\n**Done**: {response['done']}"
            f"\n**Total Duration**: {total_duration:.1f} sec"
            f"\n**Output Tokens**: {response['eval_count']} tokens"
        )
        parsed_content = self.claude._xml_to_json(response["message"]["content"])

        return {
            "raw_content": response["message"]["content"],
            "parsed_objects": parsed_content,
            "debug": debug_info,
        }

    def invoke(self, prompt_instance, tokens=4096, write_file_name=None):
        response = self.invoke_chat(
                [
                    {"role": "system", "content": prompt_instance.get_system_prompt()},
                    {"role": "user", "content": prompt_instance.get_user_prompt()},
                ],
                tokens=tokens,
            )
        markdown = "# Answer\n\n"
        markdown += response["raw_content"]
        markdown += "\n\n"
        response["cost"] = 0
        if response["parsed_objects"]:
            markdown += "# Parsed Objects\n\n```json\n"
            markdown += json.dumps(response["parsed_objects"], indent=2, sort_keys=True)
            markdown += "\n```\n\n"
        markdown += "# Metadata\n\n```json\n"
        markdown += "\n```\n\n-----\n"

        if write_file_name:
            with open(write_file_name, "w") as w:
                w.write(markdown)
        response_dir = os.path.join(os.path.dirname(__file__), "responses")
        os.makedirs(response_dir, exist_ok=True)
        file_path = os.path.join(response_dir, f"{dt.today()}.md")
        with open(file_path, "w") as w:
            w.write(markdown)
        return response
