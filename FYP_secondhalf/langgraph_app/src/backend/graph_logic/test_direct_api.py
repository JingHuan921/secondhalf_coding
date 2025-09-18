from typing import Any, Dict, List, Union, Optional, Annotated
import os
import json
import asyncio
from operator import add
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import asyncio
from dotenv import load_dotenv




async def test_openai_direct_api():
    """Test direct OpenAI API call"""
    try:
        print("DEBUG: Testing direct OpenAI API...")
        load_dotenv(override=True)

        if not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

        api_key = os.environ.get('OPENAI_API_KEY')
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Say 'DIRECT_API_OK'"}],
            "max_tokens": 10,
            "temperature": 0
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                elapsed = time.time() - start
                
                if response.status == 200:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    print(f"DEBUG: Direct API test successful in {elapsed:.2f}s: {content}")
                    return True, content
                else:
                    error_text = await response.text()
                    print(f"ERROR: Direct API test failed {response.status}: {error_text[:200]}")
                    return False, f"HTTP {response.status}"
                    
    except Exception as e:
        print(f"ERROR: Direct API test failed: {e}")
        return False, str(e)
    

# Call your async function
if __name__ == "__main__":
    asyncio.run(test_openai_direct_api())