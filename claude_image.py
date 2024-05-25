import base64
import json
import logging
from pprint import pprint as pr
import os
import time
import boto3
from botocore.exceptions import ClientError
import httpx
import cv2

logger = logging.getLogger(__name__)


class Claude3ImageWrapper:
    def __init__(self, model_id, image_media_type='image/jpeg',client=None):
        """
        :param client: A low-level client representing Amazon Bedrock Runtime.
                       Describes the API operations for running inference using Bedrock models.
                       Default: None
        """
        self.client = client
        self.model_id = model_id
        self.session_cost = 0
        self.image_media_type = image_media_type

    def _calc_cost(self, input_tokens, output_tokens):
        self.model_costs = {
            "anthropic.claude-3-sonnet-20240229-v1:0": {
                "input_cost": 0.003 * 0.001,
                "output_cost": 0.015 * 0.001,
            },
            "anthropic.claude-3-haiku-20240307-v1:0": {
                "input_cost": 0.00025 * 0.001,
                "output_cost": 0.00125 * 0.001,
            },
        }
        cost = (
            input_tokens * self.model_costs[self.model_id]["input_cost"]
            + output_tokens * self.model_costs[self.model_id]["output_cost"]
        )
        self.session_cost += cost
        cost = round(cost, 6)
        return cost

    # snippet-start:[python.example_code.bedrock-runtime.InvokeAnthropicClaude3Text]
    def invoke_claude_3_with_image(self, prompt,image_data):
        """
        Invokes Anthropic Claude 3 Sonnet to run an inference using the input
        provided in the request body.

        :param prompt: The prompt that you want Claude 3 to complete.
        :return: Inference response from the model.
        """

        # Initialize the Amazon Bedrock runtime client
        client = self.client or boto3.client(
            service_name="bedrock-runtime", region_name="us-west-2"
        )

        # Invoke Claude 3 with the text prompt

        try:
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 5000,
                        "messages": [
                            {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self.image_media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "prompt"
                }
            ],
        }
                        ],
                    }
                ),
            )

        

            # Process and print the response
            result = json.loads(response.get("body").read())
            input_tokens = result["usage"]["input_tokens"]
            output_tokens = result["usage"]["output_tokens"]
            output_list = result.get("content", [])

            # content = f"# Prompt\n{prompt}\n# Response\n"
            content = ""

            for i, output_item in enumerate(output_list):
                content += f"## Response {i+1}\n"
                content += output_item["text"] + "\n"
            output = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "content": content,
                "cost": self._calc_cost(input_tokens, output_tokens),
                "cost_str": f"{self._calc_cost(input_tokens, output_tokens)} USD",
                "session_cost": self.session_cost,
            }

            return output

        except ClientError as err:
            logger.error(
                "Couldn't invoke Claude 3 Sonnet. Here's why: %s: %s",
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def invoke(self, prompt,image_data, write_file_name=""):
        response = self.invoke_claude_3_with_image(prompt,image_data)
        if write_file_name:
            with open(write_file_name, "w") as w:
                w.write(response["content"])
                metadata = {
                    "input_tokens": response["input_tokens"],
                    "output_tokens": response["output_tokens"],
                    "cost": f"{response['cost_str']} USD",
                    "session_cost": f"{response['session_cost']} USD",
                }
                w.write("\n\n-----\n")
                w.write("```json\n")
                w.write(json.dumps(metadata, indent=2))
                w.write("\n```")
        return response


def main():
    wrapper = Claude3ImageWrapper("anthropic.claude-3-haiku-20240307-v1:0")
    previous_timestamp = None
    image_path = "input.jpeg"
    image_url = cv2.imread(image_path)
    # image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")
    with open(image_path, "rb") as f:
        image_read = f.read()
        
    image_data = base64.b64encode(image_read).decode("utf-8")

        
    while True:
        # Get the current timestamp of the input.txt file
        current_timestamp = os.path.getmtime("input.txt")

        # Check if the timestamp has changed
        if previous_timestamp != current_timestamp:
            # Read the text prompt from the file
            with open("input.txt", "r") as f:
                text_prompt = f.read()
            print(f"Invoking Claude 3 Sonnet with '{text_prompt}'...")
            wrapper.invoke(text_prompt, image_data,"output.txt")

            # Update the previous timestamp
            previous_timestamp = current_timestamp

        # Wait for 1 second before checking the file again
        time.sleep(1)


if __name__ == "__main__":
    main()
