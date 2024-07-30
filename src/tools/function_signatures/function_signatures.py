from openai import OpenAI
import prompts
import os
# from dotenv import load_do
from dotenv import load_dotenv
load_dotenv()

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

client = OpenAI(
    api_key = os.environ.get("OPENAI_API_KEY")
)

def ask_chatGPT_function_signature(source_code):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages = [
            {"role":"system", "content": "You are solidity analyzer"},
            {"role":"user", "content": source_code + "\n\n" + prompts.prompt}
        ]
    )

    # Its response time as long as 10+ seconds for a single file, how to optimize it
    return completion.choices[0].message.content

if __name__ == '__main__':
    #local test
    file_path = 'file/user/solidity/project/NFT.sol' # An OpenZepplin NFT contract
    size = os.path.getsize(file_path)
    if size > 1024 * 1024:
        raise Exception('file size exceeds 1M')
    print(file_path)
    soliditySourceCode = read_file(file_path)
    print(soliditySourceCode)
